package orchestrator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"nexus/coordinator/config"
	"nexus/coordinator/memory"
)

type Planner struct {
	cfg    *config.Config
	client *http.Client
}

type PlanStep struct {
	AgentType string         `json:"agent_type"`
	Action    string         `json:"action"`
	Params    map[string]any `json:"params"`
}

func NewPlanner(cfg *config.Config) *Planner {
	return &Planner{
		cfg: cfg,
		client: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

func (p *Planner) DecomposeObjective(ctx context.Context, obj *memory.Objective) ([]*PlanStep, error) {
	prompt := fmt.Sprintf(`You are a task planner for NEXUS, an AI assistant system.

Given the following objective, break it down into concrete action steps that can be executed by specialized agents.

Available agents and their actions:
- email_agent: read_and_summarize, reply, archive, create_filter
- calendar_agent: list_events, create_event, update_event, delete_event
- memory_agent: store, retrieve, search, delete

Objective:
Title: %s
Description: %s
Agent Type: %s

Respond with a JSON array of steps. Each step should have:
- agent_type: which agent handles this
- action: the specific action to perform
- params: parameters for the action

Example response:
[
  {"agent_type": "email_agent", "action": "read_and_summarize", "params": {"folder": "inbox", "limit": 10}},
  {"agent_type": "memory_agent", "action": "store", "params": {"key": "email_summary", "value": "..."}}
]

Respond ONLY with the JSON array, no explanation.`, obj.Title, obj.Description, obj.AgentType)

	response, err := p.callLLM(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("LLM call failed: %w", err)
	}

	var steps []*PlanStep
	if err := json.Unmarshal([]byte(response), &steps); err != nil {
		return nil, fmt.Errorf("failed to parse plan: %w", err)
	}

	return steps, nil
}

func (p *Planner) callLLM(ctx context.Context, prompt string) (string, error) {
	switch p.cfg.LLMProvider {
	case "anthropic":
		return p.callAnthropic(ctx, prompt)
	default:
		return "", fmt.Errorf("unsupported LLM provider: %s", p.cfg.LLMProvider)
	}
}

func (p *Planner) callAnthropic(ctx context.Context, prompt string) (string, error) {
	reqBody := map[string]any{
		"model":      p.cfg.LLMModel,
		"max_tokens": 2048,
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
	}

	body, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	maxRetries := 3
	var lastErr error

	for i := 0; i <= maxRetries; i++ {
		if i > 0 {
			// Exponential backoff: 1s, 2s, 4s
			time.Sleep(time.Duration(1<<uint(i-1)) * time.Second)
		}

		req, err := http.NewRequestWithContext(ctx, "POST", "https://api.anthropic.com/v1/messages", bytes.NewReader(body))
		if err != nil {
			return "", err
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("x-api-key", p.cfg.LLMAPIKey)
		req.Header.Set("anthropic-version", "2023-06-01")

		resp, err := p.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		defer resp.Body.Close()

		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = err
			continue
		}

		if resp.StatusCode != http.StatusOK {
			// Don't retry on client errors (4xx), except maybe 429 (not handling explicitly for simplicity yet)
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				return "", fmt.Errorf("API error: %s", string(respBody))
			}
			lastErr = fmt.Errorf("API error (status %d): %s", resp.StatusCode, string(respBody))
			continue
		}

		var result struct {
			Content []struct {
				Text string `json:"text"`
			} `json:"content"`
		}

		if err := json.Unmarshal(respBody, &result); err != nil {
			lastErr = err
			continue
		}

		if len(result.Content) == 0 {
			lastErr = fmt.Errorf("empty response from API")
			continue
		}

		return result.Content[0].Text, nil
	}

	return "", fmt.Errorf("max retries exceeded: %v", lastErr)
}
