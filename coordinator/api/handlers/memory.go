package handlers

import (
	"encoding/json"
	"net/http"

	"nexus/coordinator/memory"

	"github.com/go-chi/chi/v5"
)

type MemoryInput struct {
	Value    string `json:"value"`
	Category string `json:"category,omitempty"`
}

func ListMemory(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		category := r.URL.Query().Get("category")
		memories, err := store.ListMemory(category)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(memories)
	}
}

func GetMemory(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		key := chi.URLParam(r, "key")
		mem, err := store.GetMemory(key)
		if err != nil {
			http.Error(w, "Memory not found", http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(mem)
	}
}

func SetMemory(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		key := chi.URLParam(r, "key")

		var input MemoryInput
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		if input.Value == "" {
			http.Error(w, "Value is required", http.StatusBadRequest)
			return
		}

		if err := store.SetMemory(key, input.Value, input.Category); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		mem, _ := store.GetMemory(key)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(mem)
	}
}

func DeleteMemory(store *memory.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		key := chi.URLParam(r, "key")

		if err := store.DeleteMemory(key); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	}
}
