package api

import (
	"context"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"nexus/coordinator/api/handlers"
	"nexus/coordinator/config"
	"nexus/coordinator/memory"
	"nexus/coordinator/orchestrator"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/gorilla/websocket"
)

type Server struct {
	cfg    *config.Config
	store  *memory.Store
	queue  *orchestrator.Queue
	orch   *orchestrator.Orchestrator
	server *http.Server

	// WebSocket clients
	clients   map[*websocket.Conn]bool
	clientsMu sync.RWMutex
	upgrader  websocket.Upgrader
}

func NewServer(cfg *config.Config, store *memory.Store, queue *orchestrator.Queue, orch *orchestrator.Orchestrator) *Server {
	s := &Server{
		cfg:     cfg,
		store:   store,
		queue:   queue,
		orch:    orch,
		clients: make(map[*websocket.Conn]bool),
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				origin := r.Header.Get("Origin")
				for _, allowed := range cfg.AllowedOrigins {
					if allowed == origin {
						return true
					}
				}
				return false
			},
		},
	}

	router := s.setupRoutes()

	s.server = &http.Server{
		Addr:         cfg.ServerAddr,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start broadcast listener
	go s.broadcastListener()

	return s
}

func (s *Server) setupRoutes() *chi.Mux {
	r := chi.NewRouter()

	// Middleware
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))
	r.Use(s.corsMiddleware)
	r.Use(s.authMiddleware) // Applied globally to all API routes

	// API routes
	r.Route("/api", func(r chi.Router) {
		// Objectives
		r.Get("/objectives", handlers.ListObjectives(s.store))
		r.Post("/objectives", handlers.CreateObjective(s.store, s.orch))
		r.Get("/objectives/{id}", handlers.GetObjective(s.store))
		r.Put("/objectives/{id}", handlers.UpdateObjective(s.store, s.orch))
		r.Delete("/objectives/{id}", handlers.DeleteObjective(s.orch))
		r.Post("/objectives/{id}/execute", handlers.ExecuteObjective(s.orch))

		// Validations
		r.Get("/validations", handlers.ListValidations(s.store))
		r.Get("/validations/{id}", handlers.GetValidation(s.store))
		r.Post("/validations/{id}/approve", handlers.ApproveValidation(s.orch))
		r.Post("/validations/{id}/reject", handlers.RejectValidation(s.orch))

		// Activity
		r.Get("/activity", handlers.ListActivity(s.store))

		// Memory
		r.Get("/memory", handlers.ListMemory(s.store))
		r.Get("/memory/{key}", handlers.GetMemory(s.store))
		r.Put("/memory/{key}", handlers.SetMemory(s.store))
		r.Delete("/memory/{key}", handlers.DeleteMemory(s.store))
	})

	// WebSocket
	r.Get("/ws", s.handleWebSocket)

	// Static files for dashboard
	r.Handle("/*", http.FileServer(http.Dir("dashboard/static")))

	return r
}

func (s *Server) Start() error {
	return s.server.ListenAndServe()
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}

func (s *Server) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	// Verify API Key
	apiKey := r.URL.Query().Get("key")
	if apiKey != s.cfg.NexusAPIKey {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	s.clientsMu.Lock()
	s.clients[conn] = true
	s.clientsMu.Unlock()

	defer func() {
		s.clientsMu.Lock()
		delete(s.clients, conn)
		s.clientsMu.Unlock()
		conn.Close()
	}()

	// Keep connection alive and handle pings
	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
}

func (s *Server) broadcastListener() {
	for msg := range s.orch.GetBroadcastChannel() {
		s.broadcastToClients(msg)
	}
}

func (s *Server) broadcastToClients(msg *orchestrator.BroadcastMessage) {
	s.clientsMu.RLock()
	defer s.clientsMu.RUnlock()

	for client := range s.clients {
		if err := client.WriteJSON(msg); err != nil {
			log.Printf("WebSocket write error: %v", err)
			client.Close()
		}
	}
}

func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		allowed := false
		for _, o := range s.cfg.AllowedOrigins {
			if o == origin {
				allowed = true
				break
			}
		}

		if allowed {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func (s *Server) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for static files and websocket (ws auth handled separately ideally, or via cookie/token in query)
		// For now, let's keep WS open or add query param check if needed.
		// However, r.Use applies to the router it's attached to.
		// Since we attached it before all routes, it applies to everything.
		// We should probably check if the path starts with /api/
		
		if !strings.HasPrefix(r.URL.Path, "/api/") {
			next.ServeHTTP(w, r)
			return
		}

		apiKey := r.Header.Get("X-API-Key")
		if apiKey != s.cfg.NexusAPIKey {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}

		next.ServeHTTP(w, r)
	})
}
