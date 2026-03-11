package orchestrator

import (
	"context"
	"log"
	"sync"
	"time"

	"nexus/coordinator/config"
	"nexus/coordinator/memory"

	"github.com/robfig/cron/v3"
)

type Orchestrator struct {
	store    *memory.Store
	queue    *Queue
	planner  *Planner
	cfg      *config.Config
	cron     *cron.Cron
	cronJobs map[string]cron.EntryID
	mu       sync.RWMutex

	// WebSocket broadcast
	broadcast chan *BroadcastMessage
}

type BroadcastMessage struct {
	Type string `json:"type"`
	Data any    `json:"data"`
}

func New(store *memory.Store, queue *Queue, cfg *config.Config) *Orchestrator {
	return &Orchestrator{
		store:     store,
		queue:     queue,
		planner:   NewPlanner(cfg),
		cfg:       cfg,
		cron:      cron.New(cron.WithSeconds()),
		cronJobs:  make(map[string]cron.EntryID),
		broadcast: make(chan *BroadcastMessage, 100),
	}
}

func (o *Orchestrator) Start(ctx context.Context) {
	// Start cron scheduler
	o.cron.Start()

	// Load scheduled objectives
	objectives, err := o.store.ListObjectives(memory.ObjectiveStatusActive)
	if err != nil {
		log.Printf("Failed to load objectives: %v", err)
	}

	for _, obj := range objectives {
		if obj.Schedule != "" {
			o.scheduleObjective(obj)
		}
	}

	// Wait for shutdown
	<-ctx.Done()
	o.cron.Stop()
}

func (o *Orchestrator) GetBroadcastChannel() <-chan *BroadcastMessage {
	return o.broadcast
}

func (o *Orchestrator) Broadcast(msgType string, data any) {
	select {
	case o.broadcast <- &BroadcastMessage{Type: msgType, Data: data}:
	default:
		// Channel full, drop message
	}
}

func (o *Orchestrator) scheduleObjective(obj *memory.Objective) {
	o.mu.Lock()
	defer o.mu.Unlock()

	// Remove existing job if any
	if entryID, exists := o.cronJobs[obj.ID]; exists {
		o.cron.Remove(entryID)
	}

	// Add new job
	entryID, err := o.cron.AddFunc(obj.Schedule, func() {
		o.executeObjective(context.Background(), obj)
	})
	if err != nil {
		log.Printf("Failed to schedule objective %s: %v", obj.ID, err)
		return
	}

	o.cronJobs[obj.ID] = entryID
	log.Printf("Scheduled objective %s with cron: %s", obj.ID, obj.Schedule)
}

func (o *Orchestrator) ExecuteObjective(ctx context.Context, objectiveID string) error {
	obj, err := o.store.GetObjective(objectiveID)
	if err != nil {
		return err
	}
	return o.executeObjective(ctx, obj)
}

func (o *Orchestrator) executeObjective(ctx context.Context, obj *memory.Objective) error {
	log.Printf("Executing objective: %s", obj.Title)

	// Update status
	obj.Status = memory.ObjectiveStatusActive
	if err := o.store.UpdateObjective(obj); err != nil {
		return err
	}

	// Broadcast update
	o.Broadcast("objective_updated", obj)

	// Decompose objective into plans
	steps, err := o.planner.DecomposeObjective(ctx, obj)
	if err != nil {
		log.Printf("Failed to decompose objective: %v", err)
		obj.Status = memory.ObjectiveStatusFailed
		o.store.UpdateObjective(obj)
		o.Broadcast("objective_updated", obj)
		return err
	}

	// Create and dispatch plans
	for _, step := range steps {
		plan := &memory.Plan{
			ObjectiveID: obj.ID,
			AgentType:   step.AgentType,
			Action:      step.Action,
			Params:      step.Params,
			Status:      memory.PlanStatusPending,
		}

		if err := o.store.CreatePlan(plan); err != nil {
			log.Printf("Failed to create plan: %v", err)
			continue
		}

		// Dispatch to agent
		msg := &PlanMessage{
			ID:          plan.ID,
			ObjectiveID: obj.ID,
			AgentType:   step.AgentType,
			Action:      step.Action,
			Params:      step.Params,
		}

		if err := o.queue.PublishPlan(ctx, msg); err != nil {
			log.Printf("Failed to dispatch plan: %v", err)
			continue
		}

		log.Printf("Dispatched plan %s to %s: %s", plan.ID, step.AgentType, step.Action)
	}

	return nil
}

func (o *Orchestrator) HandleResult(ctx context.Context, result *ResultMessage) {
	log.Printf("Received result for plan %s: success=%v", result.PlanID, result.Success)

	plan, err := o.store.GetPlan(result.PlanID)
	if err != nil {
		log.Printf("Failed to get plan: %v", err)
		return
	}

	now := time.Now()
	plan.CompletedAt = &now

	if result.Success {
		plan.Status = memory.PlanStatusCompleted
		plan.Result = result.Result
	} else {
		plan.Status = memory.PlanStatusFailed
		plan.Error = result.Error
	}

	if err := o.store.UpdatePlan(plan); err != nil {
		log.Printf("Failed to update plan: %v", err)
	}

	// Broadcast update
	o.Broadcast("plan_updated", plan)

	// Check if all plans for objective are complete
	o.checkObjectiveCompletion(ctx, plan.ObjectiveID)
}

func (o *Orchestrator) checkObjectiveCompletion(ctx context.Context, objectiveID string) {
	// TODO: Implement logic to check if all plans are complete
	// and update objective status accordingly
}

func (o *Orchestrator) HandleValidationRequest(ctx context.Context, validation *ValidationRequestMessage) {
	log.Printf("Received validation request: %s", validation.ID)

	val := &memory.Validation{
		ID:          validation.ID,
		PlanID:      validation.PlanID,
		AgentType:   validation.AgentType,
		Action:      validation.Action,
		Description: validation.Description,
		Data:        validation.Data,
		Status:      memory.ValidationStatusPending,
		ExpiresAt:   validation.ExpiresAt,
	}

	if err := o.store.CreateValidation(val); err != nil {
		log.Printf("Failed to create validation: %v", err)
		return
	}

	// Broadcast to dashboard
	o.Broadcast("validation_request", val)
}

func (o *Orchestrator) HandleActivity(ctx context.Context, activity *ActivityMessage) {
	log.Printf("Activity from %s: %s", activity.AgentType, activity.Message)

	act := &memory.Activity{
		AgentType: activity.AgentType,
		Action:    activity.Action,
		Message:   activity.Message,
		Data:      activity.Data,
		Level:     activity.Level,
	}

	if err := o.store.CreateActivity(act); err != nil {
		log.Printf("Failed to create activity: %v", err)
		return
	}

	// Broadcast to dashboard
	o.Broadcast("activity", act)
}

func (o *Orchestrator) ApproveValidation(ctx context.Context, validationID string, response string) error {
	val, err := o.store.GetValidation(validationID)
	if err != nil {
		return err
	}

	now := time.Now()
	val.Status = memory.ValidationStatusApproved
	val.Response = response
	val.RespondedAt = &now

	if err := o.store.UpdateValidation(val); err != nil {
		return err
	}

	// Publish approval to Redis
	approval := &ApprovalMessage{
		ValidationID: validationID,
		Approved:     true,
		Response:     response,
	}

	if err := o.queue.PublishApproval(ctx, approval); err != nil {
		return err
	}

	o.Broadcast("validation_updated", val)
	return nil
}

func (o *Orchestrator) RejectValidation(ctx context.Context, validationID string, response string) error {
	val, err := o.store.GetValidation(validationID)
	if err != nil {
		return err
	}

	now := time.Now()
	val.Status = memory.ValidationStatusRejected
	val.Response = response
	val.RespondedAt = &now

	if err := o.store.UpdateValidation(val); err != nil {
		return err
	}

	// Publish rejection to Redis
	approval := &ApprovalMessage{
		ValidationID: validationID,
		Approved:     false,
		Response:     response,
	}

	if err := o.queue.PublishApproval(ctx, approval); err != nil {
		return err
	}

	o.Broadcast("validation_updated", val)
	return nil
}

func (o *Orchestrator) AddObjective(obj *memory.Objective) error {
	if err := o.store.CreateObjective(obj); err != nil {
		return err
	}

	if obj.Schedule != "" {
		o.scheduleObjective(obj)
	}

	o.Broadcast("objective_created", obj)
	return nil
}

func (o *Orchestrator) RemoveObjective(objectiveID string) error {
	o.mu.Lock()
	if entryID, exists := o.cronJobs[objectiveID]; exists {
		o.cron.Remove(entryID)
		delete(o.cronJobs, objectiveID)
	}
	o.mu.Unlock()

	if err := o.store.DeleteObjective(objectiveID); err != nil {
		return err
	}

	o.Broadcast("objective_deleted", map[string]string{"id": objectiveID})
	return nil
}
