package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"

	"nexus/coordinator/memory"
	"nexus/coordinator/orchestrator"

	"github.com/go-chi/chi/v5"
)

type ValidationResponse struct {
	Response string `json:"response,omitempty"`
}

func ListValidations(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		validations, err := store.ListPendingValidations()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(validations)
	}
}

func GetValidation(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		validation, err := store.GetValidation(id)
		if err != nil {
			http.Error(w, "Validation not found", http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(validation)
	}
}

func (v *ValidationResponse) Validate() error {
	if len(v.Response) > 1000 {
		return fmt.Errorf("response too long (max 1000 chars)")
	}
	return nil
}

func ApproveValidation(orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		var input ValidationResponse
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		if err := input.Validate(); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if err := orch.ApproveValidation(r.Context(), id, input.Response); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "approved"})
	}
}

func RejectValidation(orch *orchestrator.Orchestrator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		var input ValidationResponse
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		if err := input.Validate(); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if err := orch.RejectValidation(r.Context(), id, input.Response); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "rejected"})
	}
}
