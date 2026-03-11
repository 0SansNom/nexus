FROM golang:1.22-alpine AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache gcc musl-dev sqlite-dev

# Copy go mod files
COPY go.mod go.sum* ./
RUN go mod download

# Copy source
COPY . .

# Build
RUN CGO_ENABLED=1 go build -o nexus-coordinator .

# Runtime image
FROM alpine:3.19

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache ca-certificates sqlite-libs

# Create non-root user
RUN addgroup -S nexus && adduser -S nexus -G nexus

# Copy binary
COPY --from=builder /build/nexus-coordinator .

# Copy static files
COPY dashboard/static ./dashboard/static

# Create data directory and set permissions
RUN mkdir -p /data && chown -R nexus:nexus /data /app

EXPOSE 3000

# Switch to non-root user
USER nexus

CMD ["./nexus-coordinator"]
