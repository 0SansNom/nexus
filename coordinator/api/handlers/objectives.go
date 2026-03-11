package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"

	"nexus/coordinator/memory"
	"nexus/coordinator/orchestrator"

	"github.com/go-chi/chi/v5"
)

type ObjectiveInput struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Priority    int    `json:"priority"`
	Schedule    string `json:"schedule,omitempty"`
	AgentType   string `json:"agent_type"`
}

func ListObjectives(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		status := memory.ObjectiveStatus(r.URL.Query().Get("status"))
		objectives, err := store.ListObjectives(status)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(objectives)
	}
}

func GetObjective(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		objective, err := store.GetObjective(id)
		if err != nil {
			http.Error(w, "Objective not found", http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(objective)
	}
}

func (i *ObjectiveInput) Validate() error {
	if len(i.Title) > 100 {
		return fmt.Errorf("title too long (max 100 chars)")
	}
	if len(i.Description) > 1000 {
		return fmt.Errorf("description too long (max 1000 chars)")
	}
	if i.Priority < 0 || i.Priority > 10 {
		return fmt.Errorf("priority must be between 0 and 10")
	}
	if i.AgentType != "" {
		allowedAgents := map[string]bool{
			"email_agent":    true,
			"calendar_agent": true,
			"memory_agent":   true,
		}
		if !allowedAgents[i.AgentType] {
			return fmt.Errorf("invalid agent type: %s", i.AgentType)
		}
	}
	return nil
}

func CreateObjective(store *memory.Store, orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var input ObjectiveInput
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		if input.Title == "" {
			http.Error(w, "Title is required", http.StatusBadRequest)
			return
		}

		if input.AgentType == "" {
			http.Error(w, "Agent type is required", http.StatusBadRequest)
			return
		}

		if err := input.Validate(); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		objective := &memory.Objective{
			Title:       input.Title,
			Description: input.Description,
			Priority:    input.Priority,
			Schedule:    input.Schedule,
			AgentType:   input.AgentType,
			Status:      memory.ObjectiveStatusPending,
		}

		if err := orch.AddObjective(objective); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(objective)
	}
}

func UpdateObjective(store *memory.Store, orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		existing, err := store.GetObjective(id)
		if err != nil {
			http.Error(w, "Objective not found", http.StatusNotFound)
			return
		}

		var input ObjectiveInput
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		if err := input.Validate(); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if input.Title != "" {
			existing.Title = input.Title
		}
		if input.Description != "" {
			existing.Description = input.Description
		}
		if input.Priority != 0 {
			existing.Priority = input.Priority
		}
		if input.Schedule != "" {
			existing.Schedule = input.Schedule
		}
		if input.AgentType != "" {
			existing.AgentType = input.AgentType
		}

		if err := store.UpdateObjective(existing); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(existing)
	}
}

func DeleteObjective(orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		if err := orch.RemoveObjective(id); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	}
}

func ExecuteObjective(orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		if err := orch.ExecuteObjective(r.Context(), id); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(map[string]string{"status": "executing"})
	}
}
