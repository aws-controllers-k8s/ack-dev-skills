---
name: "wilder"
displayName: "Wilder"
description: "Wilder guide for AWS Controllers for Kubernetes (ACK) development team use"
keywords: ["ack", "aws-controllers-k8s", "kubernetes", "aws", "controllers", "code-generator", "ack-runtime", "wilder"]
author: "ACK Team"
---

# Wilder

> **Internal Tool:** This guide is specifically for Wilder use by the ACK development team and is not a customer-facing ACK project.

## Overview

Internal guide for AWS Controllers for Kubernetes (ACK) development, providing comprehensive workflows and best practices for the ACK development team. Content is distilled from ACK team discussions, code reviews, and official documentation.

**Key capabilities:**
- **Development Setup**: Environment configuration, Go version requirements, repository setup
- **Architecture Understanding**: How ACK components (runtime, code-generator, controllers) work together
- **Code Generation**: Using ack-generate and understanding templates
- **CRD Management**: Adding/modifying fields, implementing validation
- **Testing Patterns**: Team testing practices and patterns
- **Cross-Resource References**: Implementing resource relationships
- **Resource Adoption**: Adopting existing AWS resources into ACK
- **Common Patterns**: Frequently used implementation patterns from the team
- **Troubleshooting**: Common issues and solutions

**Perfect for:**
- Setting up new ACK development environments
- Implementing new ACK controllers or features
- Adding fields to existing CRDs
- Understanding ACK architecture and design decisions
- Following team best practices and patterns
- Debugging ACK controller issues
- Working with the ACK code generator

**No MCP servers required** - This is a Knowledge Base Power providing pure documentation and guidance.

## Available Steering Files

This power has the following steering file:
- **expert** - Workflow-focused development guide with step-by-step instructions for common ACK tasks

## Getting Started

### Prerequisites

Before working with ACK, ensure you have:
- **Go 1.23+** installed
- **Docker** for running tests
- **kubectl** configured for Kubernetes access
- **AWS credentials** configured

### Repository Structure

ACK is organized into multiple repositories:

**Core repositories:**
- `runtime` - Core ACK runtime library and types
- `code-generator` - Code generation tool and templates
- `test-infra` - Testing infrastructure and utilities

**Service controllers:**
- `s3-controller`, `ec2-controller`, `rds-controller`, etc.
- Each service has its own controller repository

### Quick Start

1. **Fork the repositories** you need to work with:
   ```bash
   # Fork on GitHub, then clone
   git clone https://github.com/YOUR_USERNAME/runtime
   git clone https://github.com/YOUR_USERNAME/code-generator
   ```

2. **Build the code generator**:
   ```bash
   cd code-generator
   make build-ack-generate
   ```

3. **Generate controller code**:
   ```bash
   cd ../s3-controller  # or your service
   make build-controller
   ```

## Core Concepts

### ACK Architecture

ACK consists of three main components:

1. **Runtime** - Shared library providing:
   - Base controller logic
   - AWS SDK integration
   - Common types and interfaces
   - Reconciliation framework

2. **Code Generator** - Tool that generates:
   - CRD definitions
   - Controller scaffolding
   - Type conversions
   - API bindings

3. **Service Controllers** - Individual controllers for each AWS service:
   - Built from generated code
   - Service-specific logic
   - Custom resource definitions

### Code Generation Workflow

```
AWS API Model → Code Generator → Generated Code → Controller
```

The code generator reads AWS API models and generates:
- Kubernetes CRDs
- Go types
- Controller logic
- SDK integration

### Key Principles

1. **Code generation first** - Always use ack-generate for scaffolding
2. **Runtime compatibility** - Ensure code-generator and runtime versions align
3. **Follow team patterns** - Reference decisions from tech leads and principal engineers
4. **Test thoroughly** - Follow team testing patterns
5. **Document decisions** - Add comments explaining non-obvious choices

## Common Workflows

### Adding a New Field to a CRD

1. Update the API model or generator configuration
2. Run code generation: `make build-controller`
3. Implement field mapping in custom code if needed
4. Add validation logic
5. Update tests
6. Test with real AWS resources

### Implementing Cross-Resource References

1. Define the reference field in the CRD spec
2. Use `AWSResourceReferenceWrapper` type
3. Implement resolution logic in the controller
4. Handle reference not found errors
5. Add tests for reference resolution

### Resource Adoption

1. Add adoption annotations to the resource
2. Implement adoption logic in the controller
3. Handle existing resource discovery
4. Merge existing state with desired state
5. Test adoption scenarios

## Best Practices

### Development

- **Use the latest runtime version** - Ensures compatibility and bug fixes
- **Follow Go conventions** - Standard Go project layout and naming
- **Keep generated code separate** - Don't modify generated files directly
- **Use custom hooks** - Implement custom logic in designated hook functions

### Testing

- **Unit tests** - Test individual functions and logic
- **Integration tests** - Test controller behavior with mocked AWS APIs
- **E2E tests** - Test against real AWS services (use test accounts)
- **Follow team patterns** - Reference existing tests in the codebase

### Code Reviews

- **Reference related PRs** - Link to similar changes or discussions
- **Explain non-obvious choices** - Add comments for complex logic
- **Test coverage** - Include tests for new functionality
- **Follow team feedback** - Learn from previous PR reviews

## Troubleshooting

### Common Issues

**Code generation fails:**
- Check Go version (1.23+ required)
- Verify code-generator and runtime versions match
- Check for syntax errors in custom code

**Controller doesn't reconcile:**
- Check RBAC permissions
- Verify AWS credentials
- Check controller logs for errors
- Ensure CRD is installed

**Field not appearing in CRD:**
- Verify field is in API model
- Check generator configuration
- Run code generation again
- Check for field name conflicts

**Tests failing:**
- Check test dependencies
- Verify mock setup
- Check for race conditions
- Review test logs

## Resources

### Official Documentation
- [ACK Documentation](https://aws-controllers-k8s.github.io/community/)
- [Contributing Guide](https://aws-controllers-k8s.github.io/community/docs/community/contributing/)
- [Developer Guide](https://aws-controllers-k8s.github.io/community/docs/contributor-docs/overview/)

### Key Repositories
- [Runtime](https://github.com/aws-controllers-k8s/runtime)
- [Code Generator](https://github.com/aws-controllers-k8s/code-generator)
- [Community Docs](https://github.com/aws-controllers-k8s/community)

### Team Resources
- [GitHub Discussions](https://github.com/orgs/aws-controllers-k8s/discussions)
- [Slack Channel](https://kubernetes.slack.com/archives/C01EWFWCM9X)
- [Weekly Meetings](https://aws-controllers-k8s.github.io/community/docs/community/meetings/)

## Configuration

**No authentication required** - This is a Knowledge Base Power providing documentation and guidance.

**No MCP servers** - All knowledge is embedded in the steering file.

## Support

For questions and support:
- Check the [steering file](steering/expert.md) for detailed guidance
- Review [community documentation](https://aws-controllers-k8s.github.io/community/)
- Ask in [GitHub Discussions](https://github.com/orgs/aws-controllers-k8s/discussions)
- Join the [Slack channel](https://kubernetes.slack.com/archives/C01EWFWCM9X)
