package memory

import (
	"time"
)

type ObjectiveStatus string

const (
	ObjectiveStatusPending    ObjectiveStatus = "pending"
	ObjectiveStatusActive     ObjectiveStatus = "active"
	ObjectiveStatusCompleted  ObjectiveStatus = "completed"
	ObjectiveStatusFailed     ObjectiveStatus = "failed"
	ObjectiveStatusCancelled  ObjectiveStatus = "cancelled"
)

type Objective struct {
	ID          string          `json:"id"`
	Title       string          `json:"title"`
	Description string          `json:"description"`
	Status      ObjectiveStatus `json:"status"`
	Priority    int             `json:"priority"`
	Schedule    string          `json:"schedule,omitempty"` // Cron expression
	AgentType   string          `json:"agent_type"`
	CreatedAt   time.Time       `json:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at"`
	CompletedAt *time.Time      `json:"completed_at,omitempty"`
}

type PlanStatus string

const (
	PlanStatusPending   PlanStatus = "pending"
	PlanStatusRunning   PlanStatus = "running"
	PlanStatusCompleted PlanStatus = "completed"
	PlanStatusFailed    PlanStatus = "failed"
)

type Plan struct {
	ID          string            `json:"id"`
	ObjectiveID string            `json:"objective_id"`
	AgentType   string            `json:"agent_type"`
	Action      string            `json:"action"`
	Params      map[string]any    `json:"params"`
	Status      PlanStatus        `json:"status"`
	Result      map[string]any    `json:"result,omitempty"`
	Error       string            `json:"error,omitempty"`
	CreatedAt   time.Time         `json:"created_at"`
	StartedAt   *time.Time        `json:"started_at,omitempty"`
	CompletedAt *time.Time        `json:"completed_at,omitempty"`
}

type Activity struct {
	ID        string         `json:"id"`
	AgentType string         `json:"agent_type"`
	Action    string         `json:"action"`
	Message   string         `json:"message"`
	Data      map[string]any `json:"data,omitempty"`
	Level     string         `json:"level"` // info, warning, error
	CreatedAt time.Time      `json:"created_at"`
}

type ValidationStatus string

const (
	ValidationStatusPending  ValidationStatus = "pending"
	ValidationStatusApproved ValidationStatus = "approved"
	ValidationStatusRejected ValidationStatus = "rejected"
	ValidationStatusExpired  ValidationStatus = "expired"
)

type Validation struct {
	ID          string           `json:"id"`
	PlanID      string           `json:"plan_id"`
	AgentType   string           `json:"agent_type"`
	Action      string           `json:"action"`
	Description string           `json:"description"`
	Data        map[string]any   `json:"data,omitempty"`
	Status      ValidationStatus `json:"status"`
	Response    string           `json:"response,omitempty"`
	CreatedAt   time.Time        `json:"created_at"`
	RespondedAt *time.Time       `json:"responded_at,omitempty"`
	ExpiresAt   time.Time        `json:"expires_at"`
}

type UserMemory struct {
	Key       string    `json:"key"`
	Value     string    `json:"value"`
	Category  string    `json:"category,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}
