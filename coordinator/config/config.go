package config

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	// Server
	ServerAddr string

	// Database
	DatabasePath string
	DatabaseKey  string

	// Redis
	RedisURL string

	// LLM
	LLMProvider string
	LLMModel    string
	LLMAPIKey   string

	// Security
	JWTSecret      string // Deprecated: use NexusAPIKey
	NexusAPIKey    string
	AllowedOrigins []string
}

func Load() *Config {
	return &Config{
		ServerAddr:     getEnv("SERVER_ADDR", "127.0.0.1:3000"),
		DatabasePath:   getEnv("DATABASE_PATH", "./data/nexus.db"),
		DatabaseKey:    getEnv("DATABASE_KEY", ""),
		RedisURL:       getEnv("REDIS_URL", "redis://localhost:6379"),
		LLMProvider:    getEnv("LLM_PROVIDER", "anthropic"),
		LLMModel:       getEnv("LLM_MODEL", "claude-sonnet-4-5-20250929"),
		LLMAPIKey:      getEnv("LLM_API_KEY", ""),
		NexusAPIKey:    getEnv("NEXUS_API_KEY", ""),
		AllowedOrigins: split(getEnv("ALLOWED_ORIGINS", "http://localhost:3000"), ","),
	}
}

func (c *Config) Validate() error {
	if c.LLMProvider != "mock" && c.LLMAPIKey == "" {
		return fmt.Errorf("LLM_API_KEY is required")
	}
	if c.NexusAPIKey == "" {
		return fmt.Errorf("NEXUS_API_KEY is required")
	}
	return nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func split(s, sep string) []string {
	if s == "" {
		return []string{}
	}
	return strings.Split(s, sep)
}
