---
title: Bad example
slug: bad-example
kind: new
version: 0.1
status: draft
author: Test Author
organization: Test Org
created: 2026-10-06
updated: 2026-10-06
tags: [Infra]
links: []
notion_page_id:
notion_last_sync:
notion_pending: false
---

# Software Design Description
## For Bad example

Version 0.1  
Prepared by Test Author  
Test Org  
2026-10-06

## Revision History

| Name | Date | Reason For Changes | Version |
|------|------|--------------------|---------|
| Test Author | 2026-10-06 | Initial draft | 0.1 |

## 1. Introduction

### 1.1 Document Purpose
This SDD 🚀 describes the bad example on purpose.

### 1.2 Subject Scope
The system is scalable and handles every case.

### 1.3 Definitions, Acronyms, and Abbreviations
| Term | Definition |
|------|------------|
| PR | Pull request |

### 1.4 References
Owned by {{owner team}}.

### 1.5 Document Overview
Section 3 holds the views — one per viewpoint.

### 1.6 Requirements
| ID | Requirement | Acceptance check |
|----|-------------|------------------|
| R1 | An environment is up within 10 minutes | Given a PR, when CI finishes, then healthz returns 200 |
| R2 | An environment is deleted after its PR closes |  |
| R3 | At most 15 environments run at once | Given 15 environments, when a PR opens, then CI refuses |

## 2. Design Overview

### 2.1 Stakeholder Concerns
Reviewers want a link on every PR.

### 2.2 Selected Viewpoints
Two viewpoints.

#### 2.2.1 Context
Addresses the boundary.

#### 2.2.14 Deployment
Addresses where things run.

## 3. Design Views

### V1 Context: the system
- **Viewpoint:** Context (2.2.1)
- **Implements:** R1, R2, R9
- **Decisions:** ADR-001

```mermaid
flowchart LR
	a[Dev (laptop)] --> b["GitHub"]
```

### V2 Context: a second view
- **Viewpoint:** Context (2.2.1)
- **Decisions:** none

## 4. Decisions

### ADR-001 Use one namespace per PR
- **Status:** proposed
- **Context:** each PR needs isolation (R1).
- **Options:**
  - namespace per PR
  - vcluster per PR
- **Outcome:** Chosen option: "namespace per PR", because it reuses the ingress.

### ADR-002 Use a CronJob for cleanup
- **Status:** accepted
- **Context:** cleanup must happen (R2).
- **Options:** CronJob
- **Outcome:** Chosen option: "CronJob", because it runs every 15 minutes.

## 5. Appendixes
**TODO:** add the cost sheet.
