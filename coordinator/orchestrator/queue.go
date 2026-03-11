package orchestrator

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	ChannelPlans       = "nexus:plans"
	ChannelResults     = "nexus:results"
	ChannelValidations = "nexus:validations"
	ChannelApprovals   = "nexus:approvals"
	ChannelActivity    = "nexus:activity"
)

type Queue struct {
	client *redis.Client
}

type PlanMessage struct {
	ID          string         `json:"id"`
	ObjectiveID string         `json:"objective_id"`
	AgentType   string         `json:"agent_type"`
	Action      string         `json:"action"`
	Params      map[string]any `json:"params"`
	Timestamp   time.Time      `json:"timestamp"`
}

type ResultMessage struct {
	PlanID    string         `json:"plan_id"`
	AgentType string         `json:"agent_type"`
	Success   bool           `json:"success"`
	Result    map[string]any `json:"result,omitempty"`
	Error     string         `json:"error,omitempty"`
	Timestamp time.Time      `json:"timestamp"`
}

type ValidationRequestMessage struct {
	ID          string         `json:"id"`
	PlanID      string         `json:"plan_id"`
	AgentType   string         `json:"agent_type"`
	Action      string         `json:"action"`
	Description string         `json:"description"`
	Data        map[string]any `json:"data,omitempty"`
	ExpiresAt   time.Time      `json:"expires_at"`
	Timestamp   time.Time      `json:"timestamp"`
}

type ApprovalMessage struct {
	ValidationID string    `json:"validation_id"`
	Approved     bool      `json:"approved"`
	Response     string    `json:"response,omitempty"`
	Timestamp    time.Time `json:"timestamp"`
}

type ActivityMessage struct {
	AgentType string         `json:"agent_type"`
	Action    string         `json:"action"`
	Message   string         `json:"message"`
	Data      map[string]any `json:"data,omitempty"`
	Level     string         `json:"level"`
	Timestamp time.Time      `json:"timestamp"`
}

func NewQueue(redisURL string) (*Queue, error) {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("invalid redis URL: %w", err)
	}

	client := redis.NewClient(opt)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &Queue{client: client}, nil
}

func (q *Queue) Close() error {
	return q.client.Close()
}

func (q *Queue) PublishPlan(ctx context.Context, plan *PlanMessage) error {
	plan.Timestamp = time.Now()
	data, err := json.Marshal(plan)
	if err != nil {
		return err
	}

	channel := fmt.Sprintf("%s:%s", ChannelPlans, plan.AgentType)
	return q.client.Publish(ctx, channel, data).Err()
}

func (q *Queue) PublishApproval(ctx context.Context, approval *ApprovalMessage) error {
	approval.Timestamp = time.Now()
	data, err := json.Marshal(approval)
	if err != nil {
		return err
	}
	return q.client.Publish(ctx, ChannelApprovals, data).Err()
}

func (q *Queue) StartListening(ctx context.Context, handler MessageHandler) {
	pubsub := q.client.Subscribe(ctx, ChannelResults, ChannelValidations, ChannelActivity)
	defer pubsub.Close()

	ch := pubsub.Channel()

	for {
		select {
		case <-ctx.Done():
			return
		case msg := <-ch:
			if msg == nil {
				continue
			}

			switch msg.Channel {
			case ChannelResults:
				var result ResultMessage
				if err := json.Unmarshal([]byte(msg.Payload), &result); err != nil {
					log.Printf("Failed to unmarshal result: %v", err)
					continue
				}
				handler.HandleResult(ctx, &result)

			case ChannelValidations:
				var validation ValidationRequestMessage
				if err := json.Unmarshal([]byte(msg.Payload), &validation); err != nil {
					log.Printf("Failed to unmarshal validation: %v", err)
					continue
				}
				handler.HandleValidationRequest(ctx, &validation)

			case ChannelActivity:
				var activity ActivityMessage
				if err := json.Unmarshal([]byte(msg.Payload), &activity); err != nil {
					log.Printf("Failed to unmarshal activity: %v", err)
					continue
				}
				handler.HandleActivity(ctx, &activity)
			}
		}
	}
}

type MessageHandler interface {
	HandleResult(ctx context.Context, result *ResultMessage)
	HandleValidationRequest(ctx context.Context, validation *ValidationRequestMessage)
	HandleActivity(ctx context.Context, activity *ActivityMessage)
}
