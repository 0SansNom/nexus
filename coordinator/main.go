package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"nexus/coordinator/api"
	"nexus/coordinator/config"
	"nexus/coordinator/memory"
	"nexus/coordinator/orchestrator"

	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	// Load configuration
	cfg := config.Load()
	if err := cfg.Validate(); err != nil {
		log.Fatalf("Invalid configuration: %v. LLM_API_KEY is required for non-mock providers.", err)
	}

	// Initialize SQLite store
	store, err := memory.NewStore(cfg.DatabasePath, cfg.DatabaseKey)
	if err != nil {
		log.Fatalf("Failed to initialize store: %v", err)
	}
	defer store.Close()

	// Initialize Redis queue
	queue, err := orchestrator.NewQueue(cfg.RedisURL)
	if err != nil {
		log.Fatalf("Failed to initialize Redis queue: %v", err)
	}
	defer queue.Close()

	// Initialize orchestrator
	orch := orchestrator.New(store, queue, cfg)

	// Initialize HTTP server
	server := api.NewServer(cfg, store, queue, orch)

	// Context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start orchestrator
	go orch.Start(ctx)

	// Start listening to Redis
	go queue.StartListening(ctx, orch)

	// Start HTTP server
	go func() {
		if err := server.Start(); err != nil {
			log.Fatalf("Server error: %v", err)
		}
	}()

	log.Printf("NEXUS Coordinator started on %s", cfg.ServerAddr)

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Shutting down...")
	cancel()
	server.Shutdown(ctx)
}
