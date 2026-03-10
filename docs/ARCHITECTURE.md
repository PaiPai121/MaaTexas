# Architecture Guidelines for AI-Ready Codebases

## Core Principles

### 1. Single Responsibility Principle (SRP)
Each module should have one, and only one, reason to change.

- ✅ Each module handles **ONE** clear concern.
- ❌ Monolithic modules doing everything.
- ✅ Well-defined boundaries between modules.

### 2. Deep Modularization
Modules should be deeply decomposed, not shallowly.

```text
System/
├── Core Domains/
│   ├── Domain A (e.g., Perception/User Management)
│   │   ├── Sub-domain 1
│   │   └── Sub-domain 2
│   └── Domain B (e.g., Planning/Order Processing)
└── Infrastructure/
    ├── Data Access (e.g., DB, File System)
    └── External Services (e.g., LLM APIs, Third-party APIs)
```

### 3. Clear Interfaces
Modules communicate through well-defined interfaces.

- **Contract-based design**: Explicit input/output contracts (e.g., Pydantic models, Data Classes, Typed Interfaces).
- **Type safety**: Strong typing for all interfaces.
- **Documentation**: Interface-level documentation (README, Docstrings, JSDoc, etc.).
- **Error handling**: Consistent error propagation.

### 4. Separation of Concerns
Separate domain/business logic from technical and infrastructure concerns.

- ❌ **Bad**: Domain logic mixed with direct I/O calls or database queries.
- ✅ **Good**: Domain Logic Layer → Interface/Adapter Layer → Infrastructure/External System.

### 5. Testability by Design
Architecture should make testing natural, not an afterthought.

- Dependency injection for all external dependencies.
- Mockable interfaces.
- Clear test boundaries.
- Integration test strategy.

---

## Module Structure

### Standard Module Template

```text
module_name/
├── src/
│   ├── __init__ / index      # Public API entry point
│   ├── models / types        # Data structures and type definitions
│   ├── contracts             # Interface definitions / Abstract base classes
│   ├── domain/               # Core domain logic (pure, no side effects)
│   ├── handlers/             # Input/Output handlers (API, CLI, Events)
│   ├── adapters/             # Integration with external systems
│   ├── utils/                # Utility functions
│   └── constants             # Module-level constants
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── README.md                 # Module documentation
└── module_config             # Module metadata or configuration
```

---

## AI Integration Considerations

### For LLMs
- Clear function signatures (Inputs, Outputs, Types).
- Well-documented APIs.
- Consistent naming conventions.
- Modular, testable code.

### For AI-Assisted Development
- Logical code organization.
- Consistent patterns across the codebase.
- Comprehensive documentation.
- Examples and use cases.

---

## Naming Conventions

### Modules & Directories
- Lowercase with hyphens/underscores: `user_service`, `auth-module`, `data_processor`.
- Descriptive: `payment_processing`, `notification_sender`.

### Functions & Variables
- Clear, descriptive names: `calculate_discount()`, `validate_user_token()`.
- Action-oriented verbs: `fetch`, `create`, `update`, `delete`, `extract`.

### Types & Interfaces
- PascalCase: `User`, `PaymentDetails`, `ApiResponse`.
- Descriptive: `UserRegistrationRequest`, `PaymentTransaction`.

---

## Documentation Standards

### README.md
- Module purpose.
- Usage examples.
- Dependencies.
- API reference.
- Testing instructions.

### Inline Documentation
- Standardized Docstrings/JSDoc for public APIs.
- Comments for complex or non-obvious logic.
- Type definitions acting as living documentation.

---

## Error Handling

### Consistent Error Structure
Adopt a consistent error object or exception structure across the system:

```text
Error Structure {
  code: string / int;
  message: string;
  details?: any;
  timestamp: timestamp;
}
```

### Error Propagation
- Define clear, domain-specific error types.
- Propagate errors gracefully through architectural layers.
- Handle errors explicitly at the system boundaries (e.g., logging, fallback strategies).

---

## Code Review Checklist

### Architecture
- [ ] Follows single responsibility principle.
- [ ] Proper module decomposition.
- [ ] Clear interfaces between modules.
- [ ] No circular dependencies.
- [ ] Appropriate layering.

### Quality
- [ ] Comprehensive tests.
- [ ] Type-safe code (Type hints applied).
- [ ] Consistent naming.
- [ ] Well-documented.
- [ ] Error handling properly implemented.

### AI Readiness
- [ ] Clear function signatures.
- [ ] Logical organization.
- [ ] Comprehensive examples.
- [ ] Well-defined boundaries.

---

## Maintenance

### Regular Review
- Quarterly architecture reviews.
- Dependency updates.
- Performance monitoring.
- Security audits.

### Evolution
- Incremental improvements.
- Backward compatibility.
- Deprecation strategies.
- Migration guides.
