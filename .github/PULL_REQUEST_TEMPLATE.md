## Type

<!-- Check ONE type + any applicable components -->

- [ ] **Bug fix** (fixes an issue in config generation, topology loading, or CLI behavior)
- [ ] **New feature** (adds a new CLI command, topology capability, or generation feature)
- [ ] **Enhancement** (improves existing generation logic, CLI output, or UX)
- [ ] **Breaking change** (breaks topology YAML compatibility or CLI)
- [ ] **Refactor** (internal restructuring without behavior change)
- [ ] **Documentation** (updates to guides, inline docs, or user docs)
- [ ] **Tests** (adding or updating tests)
- [ ] **CI/CD** (changes to workflows or automation)
- [ ] **Dependencies** (updates to dependencies)

## Component

<!-- Check all that apply -->

- [ ] **CLI** (Commands, options, or output formatting)
- [ ] **Core** (Application, controllers, or internal model conversion)
- [ ] **Templates** (Jinja2 templates - networkd, bird, nftables, wireguard)
- [ ] **Schema** (Topology YAML models, Pydantic validation, or config structures)

## Description

**Why is this change needed?**

<!-- Motivation and context -->

**Related Issues:** <!-- Fixes #123, Closes #123, or Relates to #123 -->

## Testing

### **Automated**

- [ ] Tests added/updated for new behavior
- [ ] `uv run pytest` passes

### **Manual**

- [ ] CLI tested locally (`uv run netloom --topology <file> <command>`)
- [ ] Generated configs reviewed (if templates changed)
- [ ] N/A — no runtime behavior changed

## Checklist

<!-- Ensure all applicable items are completed before requesting review -->

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Linter and type checker pass (`uv run ruff check .` and `uv run ty check`)
- [ ] Documentation updated (if applicable)

### Version Bumping

<!-- If changing generation behavior or CLI behavior don't forget to bump version -->

- [ ] Version bumped in `__init__.py`
