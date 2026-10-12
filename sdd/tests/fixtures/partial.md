---
title: Per-PR preview environments
slug: preview-envs
kind: new
version: 0.1
status: draft
author: Lim Eunhye
organization: Acme
created: 2026-10-06
updated: 2026-10-06
tags: [Infra, Kubernetes, CI/CD]
links: []
notion_page_id:
notion_last_sync:
notion_pending: false
---
<!-- Adapted from jam01/SDD-Template@5dca2e5 (sdd-template-bare.md), CC0 1.0. Additions: front matter, 1.6 Requirements, record formats in Sections 3 and 4. -->

# Software Design Description
## For Per-PR preview environments

Version 0.1  
Prepared by Lim Eunhye  
Acme  
2026-10-06

## Table of Contents
<!-- TOC -->
* [1. Introduction](#1-introduction)
  * [1.1 Document Purpose](#11-document-purpose)
  * [1.2 Subject Scope](#12-subject-scope)
  * [1.3 Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
  * [1.4 References](#14-references)
  * [1.5 Document Overview](#15-document-overview)
  * [1.6 Requirements](#16-requirements)
* [2. Design Overview](#2-design-overview)
  * [2.1 Stakeholder Concerns](#21-stakeholder-concerns)
  * [2.2 Selected Viewpoints](#22-selected-viewpoints)
* [3. Design Views](#3-design-views)
* [4. Decisions](#4-decisions)
* [5. Appendixes](#5-appendixes)
<!-- TOC -->

## Revision History
<!-- tracks document updates and reasons for change -->

| Name | Date | Reason For Changes | Version |
|------|------|--------------------|---------|
| Lim Eunhye | 2026-10-06 | Initial draft | 0.1 |

## 1. Introduction
<!-- overview of the SDD: purpose, scope, audience, and structure -->

### 1.1 Document Purpose
<!-- why this SDD exists, its audiences, and how they'll use it -->

### 1.2 Subject Scope
**System:** Preview environment pipeline, v1.

**Purpose:** every pull request on the web app repo gets a working copy of the app at its own URL, so reviewers can use the change before it merges.

**In scope:**
- build and deploy on PR open and on every push to the PR
- one URL per PR: `https://pr-<number>.preview.example.com`
- removal when the PR closes, plus a reaper for anything left behind
- a cap on how many environments run at once

**Out of scope:**
- production deploys
- seeding real or production data (each environment uses a fixed fixture)
- previews for backend repos (planned for v2)
- load testing

### 1.3 Definitions, Acronyms, and Abbreviations
<!-- glossary of domain terms and abbreviations; keep alphabetized -->

| Term | Definition                                                                                                               |
|------|--------------------------------------------------------------------------------------------------------------------------|
| API  | Application Programming Interface - A set of definitions and protocols for building and integrating application software |
| SDD  | Software Design Document - A document that describes the intended purpose, requirements, and nature of a software        |

### 1.4 References
<!-- external sources cited (standards, specs, docs); include title, owner, version, date, and location -->

### 1.5 Document Overview
<!-- summary of document organization and conventions -->

### 1.6 Requirements
| ID | Requirement | Acceptance check |
|----|-------------|------------------|
| R1 | While fewer than 15 environments run, a new PR gets a reachable preview environment within 10 minutes | Given 14 or fewer running environments and PR 123 opened at T0, then by T0 + 10 min `curl -fsS https://pr-123.preview.example.com/healthz` returns 200 |
| R2 | An environment is deleted within 1 hour of its PR closing | Given a closed PR, when 60 min pass, then `kubectl get ns pr-123` returns NotFound |
| R3 | A preview environment cannot reach production databases | Given a running environment, when a Job in namespace pr-123 runs `nc -z -w 3 <ip> 5432` against each production database IP, then every connection fails, while the same Job can connect to the environment's own Postgres |
| R4 | At most 15 preview environments run at once | Given 15 running environments, when a 16th PR opens, then CI comments "preview capacity full" on the PR and creates no namespace |

## 2. Design Overview
<!-- describes the system’s architecture and design approach -->

### 2.1 Stakeholder Concerns
**TODO:** list the stakeholders once the web team confirms who reviews previews.

### 2.2 Selected Viewpoints
<!-- lists viewpoints used to describe the system, their purpose, and addressed concerns -->

#### 2.2.1 Context
<!-- system boundaries, external actors, and interactions -->

#### 2.2.2 Composition
<!-- major components/subsystems and how they are organized -->

#### 2.2.3 Logical
<!-- main abstractions (classes, interfaces) and relationships -->

#### 2.2.4 Physical
<!-- hardware topology and infrastructure constraints -->

#### 2.2.5 Structure
<!-- internal organization of components and connectors -->

#### 2.2.6 Dependency
<!-- relationships and dependencies among design elements -->

#### 2.2.7 Information
<!-- data structures, persistence, and data management -->

#### 2.2.8 Interface
<!-- contracts between components or with external systems -->

#### 2.2.9 Interaction
<!-- runtime message flow and collaboration among components -->

#### 2.2.10 Algorithm
<!-- processing logic, steps, and key computations -->

#### 2.2.11 State Dynamics
<!-- states, transitions, and events affecting system behavior -->

#### 2.2.12 Concurrency
<!-- handling of parallelism, synchronization, and ordering -->

#### 2.2.13 Patterns
<!-- design or architectural patterns applied and their roles -->

#### 2.2.14 Deployment
<!-- mapping of software components to physical nodes or environments -->

#### 2.2.15 Resources
<!-- resource use, allocation, and management (e.g., memory, threads) -->

## 3. Design Views
<!-- detailed architectural and design elements, diagrams, and rationale -->
<!-- one record per view:
### V<n> <Viewpoint>: <title>
- **Viewpoint:** <name> (2.2.<n>)
- **Implements:** <requirement IDs from 1.6, or "none" and why>
- **Decisions:** <ADR IDs, or "none">

<diagram: mermaid flowchart TB, sequenceDiagram, erDiagram, stateDiagram-v2, or a table>

<what the diagram shows and what it leaves out, 1 to 6 lines>

- **More information:** <links>
-->

## 4. Decisions
<!-- major design or architectural choices and their justifications -->
<!-- one record per decision (MADR style):
### ADR-<nnn> <short title: the problem and the chosen solution>
- **Status:** proposed | accepted
- **Context:** <the problem and the forces, with requirement IDs>
- **Options:**
  - <option 1>
  - <option 2>
- **Outcome:** Chosen option: "<option>", because <reason>.
- **More information:** <views and links>
-->

## 5. Appendixes
_Not applicable: no supporting material for v1._
