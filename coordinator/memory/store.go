package memory

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/mattn/go-sqlite3"
)

type Store struct {
	db *sql.DB
}

func NewStore(dbPath, encryptionKey string) (*Store, error) {
	dsn := dbPath
	if encryptionKey != "" {
		dsn = fmt.Sprintf("%s?_pragma_key=%s&_pragma_cipher_page_size=4096", dbPath, encryptionKey)
	}

	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	store := &Store{db: db}
	if err := store.migrate(); err != nil {
		return nil, fmt.Errorf("failed to migrate database: %w", err)
	}

	return store, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) migrate() error {
	schema := `
	CREATE TABLE IF NOT EXISTS objectives (
		id TEXT PRIMARY KEY,
		title TEXT NOT NULL,
		description TEXT,
		status TEXT NOT NULL DEFAULT 'pending',
		priority INTEGER DEFAULT 0,
		schedule TEXT,
		agent_type TEXT NOT NULL,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		completed_at DATETIME
	);

	CREATE TABLE IF NOT EXISTS plans (
		id TEXT PRIMARY KEY,
		objective_id TEXT NOT NULL,
		agent_type TEXT NOT NULL,
		action TEXT NOT NULL,
		params TEXT,
		status TEXT NOT NULL DEFAULT 'pending',
		result TEXT,
		error TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		started_at DATETIME,
		completed_at DATETIME,
		FOREIGN KEY (objective_id) REFERENCES objectives(id)
	);

	CREATE TABLE IF NOT EXISTS activity (
		id TEXT PRIMARY KEY,
		agent_type TEXT NOT NULL,
		action TEXT NOT NULL,
		message TEXT NOT NULL,
		data TEXT,
		level TEXT DEFAULT 'info',
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS validations (
		id TEXT PRIMARY KEY,
		plan_id TEXT NOT NULL,
		agent_type TEXT NOT NULL,
		action TEXT NOT NULL,
		description TEXT NOT NULL,
		data TEXT,
		status TEXT NOT NULL DEFAULT 'pending',
		response TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		responded_at DATETIME,
		expires_at DATETIME NOT NULL,
		FOREIGN KEY (plan_id) REFERENCES plans(id)
	);

	CREATE TABLE IF NOT EXISTS user_memory (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL,
		category TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);

	CREATE INDEX IF NOT EXISTS idx_objectives_status ON objectives(status);
	CREATE INDEX IF NOT EXISTS idx_plans_objective_id ON plans(objective_id);
	CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
	CREATE INDEX IF NOT EXISTS idx_activity_created_at ON activity(created_at);
	CREATE INDEX IF NOT EXISTS idx_validations_status ON validations(status);
	CREATE INDEX IF NOT EXISTS idx_user_memory_category ON user_memory(category);
	`

	_, err := s.db.Exec(schema)
	return err
}

// Objectives CRUD

func (s *Store) CreateObjective(obj *Objective) error {
	obj.ID = uuid.New().String()
	obj.CreatedAt = time.Now()
	obj.UpdatedAt = time.Now()
	if obj.Status == "" {
		obj.Status = ObjectiveStatusPending
	}

	_, err := s.db.Exec(`
		INSERT INTO objectives (id, title, description, status, priority, schedule, agent_type, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		obj.ID, obj.Title, obj.Description, obj.Status, obj.Priority, obj.Schedule, obj.AgentType, obj.CreatedAt, obj.UpdatedAt)
	return err
}

func (s *Store) GetObjective(id string) (*Objective, error) {
	obj := &Objective{}
	var completedAt sql.NullTime

	err := s.db.QueryRow(`
		SELECT id, title, description, status, priority, schedule, agent_type, created_at, updated_at, completed_at
		FROM objectives WHERE id = ?`, id).Scan(
		&obj.ID, &obj.Title, &obj.Description, &obj.Status, &obj.Priority, &obj.Schedule, &obj.AgentType, &obj.CreatedAt, &obj.UpdatedAt, &completedAt)
	if err != nil {
		return nil, err
	}
	if completedAt.Valid {
		obj.CompletedAt = &completedAt.Time
	}
	return obj, nil
}

func (s *Store) ListObjectives(status ObjectiveStatus) ([]*Objective, error) {
	query := `SELECT id, title, description, status, priority, schedule, agent_type, created_at, updated_at, completed_at FROM objectives`
	args := []any{}

	if status != "" {
		query += " WHERE status = ?"
		args = append(args, status)
	}
	query += " ORDER BY priority DESC, created_at DESC"

	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var objectives []*Objective
	for rows.Next() {
		obj := &Objective{}
		var completedAt sql.NullTime
		if err := rows.Scan(&obj.ID, &obj.Title, &obj.Description, &obj.Status, &obj.Priority, &obj.Schedule, &obj.AgentType, &obj.CreatedAt, &obj.UpdatedAt, &completedAt); err != nil {
			return nil, err
		}
		if completedAt.Valid {
			obj.CompletedAt = &completedAt.Time
		}
		objectives = append(objectives, obj)
	}
	return objectives, nil
}

func (s *Store) UpdateObjective(obj *Objective) error {
	obj.UpdatedAt = time.Now()
	_, err := s.db.Exec(`
		UPDATE objectives SET title = ?, description = ?, status = ?, priority = ?, schedule = ?, agent_type = ?, updated_at = ?, completed_at = ?
		WHERE id = ?`,
		obj.Title, obj.Description, obj.Status, obj.Priority, obj.Schedule, obj.AgentType, obj.UpdatedAt, obj.CompletedAt, obj.ID)
	return err
}

func (s *Store) DeleteObjective(id string) error {
	_, err := s.db.Exec("DELETE FROM objectives WHERE id = ?", id)
	return err
}

// Plans CRUD

func (s *Store) CreatePlan(plan *Plan) error {
	plan.ID = uuid.New().String()
	plan.CreatedAt = time.Now()
	if plan.Status == "" {
		plan.Status = PlanStatusPending
	}

	paramsJSON, _ := json.Marshal(plan.Params)

	_, err := s.db.Exec(`
		INSERT INTO plans (id, objective_id, agent_type, action, params, status, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)`,
		plan.ID, plan.ObjectiveID, plan.AgentType, plan.Action, paramsJSON, plan.Status, plan.CreatedAt)
	return err
}

func (s *Store) GetPlan(id string) (*Plan, error) {
	plan := &Plan{}
	var paramsJSON, resultJSON sql.NullString
	var startedAt, completedAt sql.NullTime

	err := s.db.QueryRow(`
		SELECT id, objective_id, agent_type, action, params, status, result, error, created_at, started_at, completed_at
		FROM plans WHERE id = ?`, id).Scan(
		&plan.ID, &plan.ObjectiveID, &plan.AgentType, &plan.Action, &paramsJSON, &plan.Status, &resultJSON, &plan.Error, &plan.CreatedAt, &startedAt, &completedAt)
	if err != nil {
		return nil, err
	}

	if paramsJSON.Valid {
		json.Unmarshal([]byte(paramsJSON.String), &plan.Params)
	}
	if resultJSON.Valid {
		json.Unmarshal([]byte(resultJSON.String), &plan.Result)
	}
	if startedAt.Valid {
		plan.StartedAt = &startedAt.Time
	}
	if completedAt.Valid {
		plan.CompletedAt = &completedAt.Time
	}

	return plan, nil
}

func (s *Store) UpdatePlan(plan *Plan) error {
	resultJSON, _ := json.Marshal(plan.Result)
	_, err := s.db.Exec(`
		UPDATE plans SET status = ?, result = ?, error = ?, started_at = ?, completed_at = ?
		WHERE id = ?`,
		plan.Status, resultJSON, plan.Error, plan.StartedAt, plan.CompletedAt, plan.ID)
	return err
}

// Activity CRUD

func (s *Store) CreateActivity(act *Activity) error {
	act.ID = uuid.New().String()
	act.CreatedAt = time.Now()

	dataJSON, _ := json.Marshal(act.Data)

	_, err := s.db.Exec(`
		INSERT INTO activity (id, agent_type, action, message, data, level, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)`,
		act.ID, act.AgentType, act.Action, act.Message, dataJSON, act.Level, act.CreatedAt)
	return err
}

func (s *Store) ListActivity(limit int) ([]*Activity, error) {
	if limit <= 0 {
		limit = 100
	}

	rows, err := s.db.Query(`
		SELECT id, agent_type, action, message, data, level, created_at
		FROM activity ORDER BY created_at DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var activities []*Activity
	for rows.Next() {
		act := &Activity{}
		var dataJSON sql.NullString
		if err := rows.Scan(&act.ID, &act.AgentType, &act.Action, &act.Message, &dataJSON, &act.Level, &act.CreatedAt); err != nil {
			return nil, err
		}
		if dataJSON.Valid {
			json.Unmarshal([]byte(dataJSON.String), &act.Data)
		}
		activities = append(activities, act)
	}
	return activities, nil
}

// Validations CRUD

func (s *Store) CreateValidation(val *Validation) error {
	val.ID = uuid.New().String()
	val.CreatedAt = time.Now()
	if val.ExpiresAt.IsZero() {
		val.ExpiresAt = time.Now().Add(24 * time.Hour)
	}

	dataJSON, _ := json.Marshal(val.Data)

	_, err := s.db.Exec(`
		INSERT INTO validations (id, plan_id, agent_type, action, description, data, status, expires_at, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		val.ID, val.PlanID, val.AgentType, val.Action, val.Description, dataJSON, val.Status, val.ExpiresAt, val.CreatedAt)
	return err
}

func (s *Store) GetValidation(id string) (*Validation, error) {
	val := &Validation{}
	var dataJSON sql.NullString
	var respondedAt sql.NullTime

	err := s.db.QueryRow(`
		SELECT id, plan_id, agent_type, action, description, data, status, response, created_at, responded_at, expires_at
		FROM validations WHERE id = ?`, id).Scan(
		&val.ID, &val.PlanID, &val.AgentType, &val.Action, &val.Description, &dataJSON, &val.Status, &val.Response, &val.CreatedAt, &respondedAt, &val.ExpiresAt)
	if err != nil {
		return nil, err
	}

	if dataJSON.Valid {
		json.Unmarshal([]byte(dataJSON.String), &val.Data)
	}
	if respondedAt.Valid {
		val.RespondedAt = &respondedAt.Time
	}

	return val, nil
}

func (s *Store) ListPendingValidations() ([]*Validation, error) {
	rows, err := s.db.Query(`
		SELECT id, plan_id, agent_type, action, description, data, status, response, created_at, responded_at, expires_at
		FROM validations WHERE status = 'pending' AND expires_at > CURRENT_TIMESTAMP
		ORDER BY created_at ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var validations []*Validation
	for rows.Next() {
		val := &Validation{}
		var dataJSON sql.NullString
		var respondedAt sql.NullTime
		if err := rows.Scan(&val.ID, &val.PlanID, &val.AgentType, &val.Action, &val.Description, &dataJSON, &val.Status, &val.Response, &val.CreatedAt, &respondedAt, &val.ExpiresAt); err != nil {
			return nil, err
		}
		if dataJSON.Valid {
			json.Unmarshal([]byte(dataJSON.String), &val.Data)
		}
		if respondedAt.Valid {
			val.RespondedAt = &respondedAt.Time
		}
		validations = append(validations, val)
	}
	return validations, nil
}

func (s *Store) UpdateValidation(val *Validation) error {
	_, err := s.db.Exec(`
		UPDATE validations SET status = ?, response = ?, responded_at = ?
		WHERE id = ?`,
		val.Status, val.Response, val.RespondedAt, val.ID)
	return err
}

// User Memory CRUD

func (s *Store) SetMemory(key, value, category string) error {
	now := time.Now()
	_, err := s.db.Exec(`
		INSERT INTO user_memory (key, value, category, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET value = ?, category = ?, updated_at = ?`,
		key, value, category, now, now, value, category, now)
	return err
}

func (s *Store) GetMemory(key string) (*UserMemory, error) {
	mem := &UserMemory{}
	err := s.db.QueryRow(`
		SELECT key, value, category, created_at, updated_at
		FROM user_memory WHERE key = ?`, key).Scan(
		&mem.Key, &mem.Value, &mem.Category, &mem.CreatedAt, &mem.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return mem, nil
}

func (s *Store) ListMemory(category string) ([]*UserMemory, error) {
	query := "SELECT key, value, category, created_at, updated_at FROM user_memory"
	args := []any{}

	if category != "" {
		query += " WHERE category = ?"
		args = append(args, category)
	}
	query += " ORDER BY key"

	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var memories []*UserMemory
	for rows.Next() {
		mem := &UserMemory{}
		if err := rows.Scan(&mem.Key, &mem.Value, &mem.Category, &mem.CreatedAt, &mem.UpdatedAt); err != nil {
			return nil, err
		}
		memories = append(memories, mem)
	}
	return memories, nil
}

func (s *Store) DeleteMemory(key string) error {
	_, err := s.db.Exec("DELETE FROM user_memory WHERE key = ?", key)
	return err
}
