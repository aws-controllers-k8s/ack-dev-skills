# Setting Up ACK Development Environment

## Prerequisites

- **Go 1.23+**: `go version`
- **Docker**: `docker --version`
- **kubectl** configured: `kubectl version`
- **AWS credentials** configured: `aws sts get-caller-identity`

## Steps

1. **Clone core repos:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/code-generator
   git clone https://github.com/YOUR_USERNAME/runtime
   ```

2. **Build code-generator:**
   ```bash
   cd code-generator
   make build-ack-generate
   ```

3. **Clone your service controller:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/<service>-controller
   ```

4. **Verify:**
   ```bash
   ./bin/ack-generate --help
   cd <service>-controller && make test
   ```

## Common Setup Issues

- **Go version mismatch**: ACK requires Go 1.23+. Check `go.mod`.
- **Runtime version mismatch**: Ensure code-generator and runtime versions align.
- **Build fails**: Run `go mod tidy` and retry.

## Repository Structure

ACK is organized into multiple repositories:

**Core repositories:**
- `runtime` - Core ACK runtime library and types
- `code-generator` - Code generation tool and templates
- `test-infra` - Testing infrastructure and utilities

**Service controllers:**
- `s3-controller`, `ec2-controller`, `rds-controller`, etc.
- Each service has its own controller repository
