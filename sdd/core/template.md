---
title: {{project name}}
slug: {{slug}}
kind: {{kind}}
version: 0.1
status: draft
author: {{author}}
organization: {{organization}}
created: {{date_modified}}
updated: {{date_modified}}
tags: {{tags}}
links: {{links}}
notion_page_id:
notion_last_sync:
notion_pending: false
---
<!-- Adapted from jam01/SDD-Template@5dca2e5 (sdd-template-bare.md), CC0 1.0. Additions: front matter, 1.6 Requirements, record formats in Sections 3 and 4. -->

# Software Design Description
## For {{project name}}

Version 0.1  
Prepared by {{author}}  
{{organization}}  
{{date_modified}}

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
|      |      |                    |         |
|      |      |                    |         |

## 1. Introduction
<!-- overview of the SDD: purpose, scope, audience, and structure -->

### 1.1 Document Purpose
<!-- why this SDD exists, its audiences, and how they'll use it -->

### 1.2 Subject Scope
<!-- identifies the system being designed, its purpose, boundaries, and main functions -->

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
<!-- what the system must do: one row per requirement, each with a check that proves it (Given/When/Then, or a command and its expected result) -->

| ID | Requirement | Acceptance check |
|----|-------------|------------------|

## 2. Design Overview
<!-- describes the system’s architecture and design approach -->

### 2.1 Stakeholder Concerns
<!-- identifies stakeholders and their main design-related interests -->

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
<!-- supporting material such as models, datasets, or references -->
