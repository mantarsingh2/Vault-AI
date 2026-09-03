# Vault AI — System Architecture

**Project:** Vault AI
**Document:** System Architecture
**Version:** 1.0
**Architecture Type:** Local-First, Resource-Aware AI Desktop Agent

---

# 1. Architecture Overview

Vault AI is designed as a modular AI desktop-agent system.

The architecture separates:

* User interaction
* Application logic
* AI reasoning
* AI orchestration
* Resource management
* Safety and permissions
* Tool execution
* Functional modules
* Data and memory
* Operating-system interaction
* Hardware/resource monitoring

The high-level architecture is:

```text
                    ┌──────────────────────┐
                    │        USER          │
                    │  Text / Voice Input  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     PySide6 GUI      │
                    │ Desktop Application  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Query / Intent Router│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      LangGraph       │
                    │ AI Orchestration     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
      ┌──────────────┐ ┌───────────────┐ ┌───────────────┐
      │ AI Model     │ │ Resource      │ │ AI Guardian   │
      │ Manager      │ │ Manager       │ │ / Policy      │
      └──────┬───────┘ └───────┬───────┘ └───────┬───────┘
             │                 │                 │
             ▼                 ▼                 ▼
       Local / Cloud      Load / Unload       Permission
           Models          Modules             / Safety
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Tool / Execution     │
                    │ Manager              │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Functional Modules   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Operating System  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Hardware / Resources │
                    └──────────────────────┘
```

---

# 2. Three Major Architecture Areas

Vault AI can be understood as three major areas:

```text
┌───────────────────────────────────────────────────────────┐
│                         VAULT AI                           │
│                                                           │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────┐ │
│  │      USER      │   │  APPLICATION   │   │    DATA    │ │
│  │                │   │                │   │            │ │
│  │ Text           │   │ PySide6        │   │ SQLite     │ │
│  │ Voice          │   │ Router         │   │ Memory     │ │
│  │ Commands       │   │ LangGraph      │   │ ChromaDB   │ │
│  └────────────────┘   │ Guardian       │   │ Logs       │ │
│                       │ Resource Mgr   │   │ RAG        │ │
│                       │ Execution      │   │            │ │
│                       └────────────────┘   └────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

These areas are interconnected.

---

# 3. User Layer

The User Layer is the entry point to Vault AI.

The user may interact through:

```text
Text
Voice
```

## Text

The user enters a command through the PySide6 interface.

Example:

```text
Open VS Code and open my project.
```

## Voice

Voice input can use:

```text
Faster-Whisper
```

The voice is converted into text before entering the command-processing pipeline.

---

# 4. Application Layer

The Application Layer contains the main intelligence and control components.

It includes:

```text
PySide6
Query / Intent Router
LangGraph
AI Model Manager
Resource Manager
AI Guardian
Tool / Execution Manager
Functional Modules
```

This layer controls how a user request becomes an actual desktop operation.

---

# 5. Data Layer

The Data Layer stores structured information, memory, logs, and searchable knowledge.

Planned technologies include:

```text
SQLite
ChromaDB
LlamaIndex
BGE Embeddings
```

The Data Layer may contain:

```text
User Data
Settings
Task History
Execution Logs
Permissions
Memory
Documents
Embeddings
Application State
```

---

# 6. Query / Intent Router

The Query / Intent Router is the first intelligence component after user input.

Its responsibility is to determine what type of request the user has made.

Example:

```text
User:
Check my RAM usage.
```

The router identifies this as:

```text
System Monitoring
```

Another example:

```text
User:
Read this screenshot.
```

The router identifies:

```text
Vision / OCR
```

Another:

```text
User:
Search the latest information about Python.
```

The router identifies:

```text
Internet / Knowledge
```

The router sends the request into the appropriate orchestration path.

---

# 7. LangGraph — AI Orchestration Layer

LangGraph is the orchestration layer.

Its responsibility is to manage multi-step workflows.

For a simple request:

```text
User
 ↓
LangGraph
 ↓
Tool
 ↓
Result
```

For a complex request:

```text
User
 ↓
LangGraph
 ↓
Create Plan
 ↓
Step 1
 ↓
Step 2
 ↓
Step 3
 ↓
Verification
 ↓
Final Result
```

LangGraph should maintain the state of the workflow and determine which stage should execute next.

---

# 8. Planning

Complex tasks should be converted into an explicit plan before execution.

Example:

```text
User:

Setup Python for VS Code,
open this file,
attach it to the project,
and check hardware compatibility.
```

The planner may generate:

```text
1. Check hardware
2. Check Python installation
3. Install Python if required
4. Install VS Code extension if required
5. Open VS Code
6. Open project folder
7. Open requested file
8. Verify configuration
```

The plan does not mean every action should execute simultaneously.

---

# 9. Sequential Execution

The default behavior for dependent tasks should be sequential.

```text
Plan
 ↓
Hardware Check
 ↓
Install Python
 ↓
Verify Python
 ↓
Install VS Code
 ↓
Verify VS Code
 ↓
Open Project
 ↓
Open File
 ↓
Verify
 ↓
Complete
```

A later step should normally wait for the required earlier step to finish successfully.

---

# 10. Parallel Execution

Parallel execution is allowed only when operations are independent and the Resource Manager determines that sufficient resources are available.

Example:

```text
Check CPU
       \
        → Resource Analysis
       /
Check RAM
```

But tasks with dependencies should remain sequential.

Example:

```text
Install Python
      ↓
Verify Python
      ↓
Configure Python
```

These should not be executed simultaneously.

---

# 11. AI Model Manager

The AI Model Manager controls which AI model/provider should be used.

The planned model sources are:

```text
Local:
Ollama → Qwen

Cloud:
OpenRouter
```

The decision may depend on:

* Task requirements.
* Model capabilities.
* Available hardware.
* RAM.
* CPU.
* GPU availability.
* Local model availability.
* Cloud availability.
* Resource constraints.

Conceptually:

```text
                    Request
                       ↓
                AI Model Manager
                  /           \
                 /             \
                ▼               ▼
          Ollama / Qwen     OpenRouter
             Local             Cloud
```

The detailed model-selection rules belong in `RULES.md`.

---

# 12. Dynamic Resource Manager

The Dynamic Resource Manager is a central architectural component.

Its purpose is to prevent Vault AI from unnecessarily consuming system resources.

It is responsible for:

```text
Resource Detection
Module Selection
Module Loading
Module Unloading
Task Scheduling
Resource Optimization
Parallelism Control
Model Routing Support
```

---

# 13. Why the Resource Manager Is Needed

A poorly designed agent could load:

```text
Whisper
OpenCV
EasyOCR
Docker
Playwright
Qwen
Piper
FastAPI
```

all at the same time.

This can create unnecessary resource consumption.

Vault AI instead follows:

```text
Task
 ↓
Determine Required Capabilities
 ↓
Check Available Resources
 ↓
Load Only Required Modules
 ↓
Execute
 ↓
Release Unneeded Resources
```

---

# 14. Resource Monitoring

The Resource Manager should monitor available resources.

The planned monitoring technology includes:

```text
psutil
```

Potential resources include:

```text
CPU
RAM
Storage
Processes
```

GPU availability may also be considered where supported by the implementation.

---

# 15. Dynamic / Lazy Module Loading

Vault AI should load capabilities only when required.

## Example — Hardware Check

User:

```text
Check my hardware.
```

Required capability:

```text
psutil
```

The system should not load:

```text
OpenCV
EasyOCR
Whisper
Piper
Playwright
Docker
```

---

## Example — Screenshot Reading

User:

```text
Read this screenshot and explain the error.
```

Required capabilities may include:

```text
OpenCV
EasyOCR
Qwen
```

These components remain available for the task.

Unrelated capabilities should remain unloaded.

---

# 16. Resource Lifecycle

A module follows a lifecycle similar to:

```text
AVAILABLE
    ↓
REQUESTED
    ↓
RESOURCE CHECK
    ↓
LOAD
    ↓
ACTIVE
    ↓
TASK EXECUTION
    ↓
VERIFICATION
    ↓
RELEASE
    ↓
INACTIVE
```

The Resource Manager controls this lifecycle.

---

# 17. Resource-Constrained Execution

If available resources are insufficient, Vault AI may select another strategy.

Possible strategies include:

```text
Use smaller local model
        OR
Use OpenRouter/cloud model
        OR
Queue the task
        OR
Reduce parallel execution
        OR
Ask user to free system resources
```

The exact policy should be defined by `RULES.md`.

---

# 18. AI Guardian

The AI Guardian provides a safety and policy layer.

It should inspect proposed operations before sensitive execution.

Example:

```text
AI creates action
       ↓
AI Guardian
       ↓
Risk / Policy Check
       ↓
Permission Required?
       ↓
User Approval
       ↓
Execution
```

The Guardian should help prevent unsafe or unintended operations.

---

# 19. Permission System

Operations can be categorized according to their risk.

Conceptually:

```text
Low Risk
   ↓
May execute automatically

Medium Risk
   ↓
Policy-dependent

High Risk
   ↓
Require explicit user approval
```

Examples of potentially sensitive actions include:

```text
Delete files
Install software
Change system configuration
Network isolation
Security operations
```

The exact classification belongs in `RULES.md`.

---

# 20. Tool / Execution Manager

The Tool / Execution Manager separates AI reasoning from actual execution.

The AI may determine:

```text
I need to open VS Code.
```

But the AI should not directly execute arbitrary system instructions.

Instead:

```text
AI
 ↓
Tool Selection
 ↓
AI Guardian
 ↓
Execution Manager
 ↓
Application Tool
 ↓
Operating System
```

This provides a controlled boundary between reasoning and execution.

---

# 21. Functional Modules

Vault AI uses specialized functional modules.

Potential modules include:

```text
File Manager
System Monitor
Application Manager
Browser Automation
Vision / OCR
Voice Input
Voice Output
Security
Knowledge / RAG
```

Each module should expose controlled functionality to the Execution Manager.

---

# 22. File Management Module

The file-management capability can use Python filesystem functionality such as:

```text
pathlib
shutil
```

Potential operations:

```text
List
Copy
Move
Delete
Organize
```

---

# 23. System Monitoring Module

The system-monitoring module uses:

```text
psutil
```

Potential information:

```text
CPU
RAM
Storage
Processes
```

This module is also important to the Resource Manager because resource information can influence execution decisions.

---

# 24. Application Execution Module

The planned mechanism for controlled process/application execution includes:

```text
subprocess
```

Example:

```text
User:
Open VS Code.

AI
 ↓
Application Tool
 ↓
subprocess
 ↓
Operating System
 ↓
VS Code
```

---

# 25. Browser Automation Module

Browser automation uses:

```text
Playwright
```

It should be dynamically loaded only when browser interaction is required.

Example:

```text
User:
Open the website and download my report.

 ↓

Playwright Module
 ↓
Browser
 ↓
Download
 ↓
Verify
```

---

# 26. Vision Module

The vision/OCR stack includes:

```text
OpenCV
EasyOCR
```

Example:

```text
Screenshot
 ↓
OpenCV
 ↓
EasyOCR
 ↓
Extracted Text
 ↓
Qwen
 ↓
Explanation
```

These modules should not be loaded for unrelated tasks.

---

# 27. Voice Module

Voice input:

```text
Faster-Whisper
```

Voice output:

```text
Piper
```

The intended architecture is:

```text
Voice
 ↓
Faster-Whisper
 ↓
Text
 ↓
AI Pipeline
 ↓
Response
 ↓
Piper
 ↓
Voice
```

---

# 28. Knowledge / RAG Layer

Vault AI includes a retrieval and knowledge-processing layer.

The planned components are:

```text
LlamaIndex
     ↓
ChromaDB
     ↓
BGE Embeddings
```

Conceptually:

```text
Documents
 ↓
LlamaIndex
 ↓
BGE Embeddings
 ↓
ChromaDB
 ↓
Retrieve Relevant Information
 ↓
LLM
 ↓
Response
```

---

# 29. Data Storage

SQLite is intended for structured application data.

Potential tables/data areas include:

```text
Users
Settings
Tasks
Task History
Permissions
Logs
Application State
Memory Metadata
```

The exact database schema should be defined separately from the architecture.

---

# 30. Memory Architecture

Vault AI may maintain memory for:

```text
Task History
User Preferences
Relevant Context
Previous Operations
Knowledge References
```

The detailed memory strategy belongs in:

```text
MEMORY.md
```

---

# 31. Verification Layer

After an action is executed, Vault AI should verify the result.

Example:

```text
Install Python
      ↓
Execution
      ↓
Check Python Version
      ↓
Verification
      ↓
Success
```

If verification fails:

```text
Execution
      ↓
Verification
      ↓
Failure
      ↓
Error Handling
      ↓
Retry / Report
```

---

# 32. Logging

The system should record important events.

Example:

```text
Timestamp:
User Request:
Plan:
Selected Tool:
Permission:
Execution:
Verification:
Result:
Error:
```

Logs can be used for:

* Debugging.
* Task history.
* Security.
* Auditing.
* Project analysis.

---

# 33. Complete Request Lifecycle

The complete architecture can be represented as:

```text
                    USER
                      │
                      ▼
              ┌───────────────┐
              │    PySide6    │
              │      GUI      │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ Query / Intent│
              │     Router    │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │   LangGraph   │
              │ Orchestration │
              └───────┬───────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       AI Model   Resource     AI Guardian
       Manager     Manager        │
          │           │           │
          ▼           ▼           ▼
       Qwen /      Modules     Permission
      OpenRouter   Resources      │
          │           │           │
          └───────────┼───────────┘
                      │
                      ▼
             Tool / Execution
                  Manager
                      │
                      ▼
             Functional Module
                      │
                      ▼
              Operating System
                      │
                      ▼
                  Hardware
                      │
                      ▼
                Verification
                      │
                      ▼
                    Logs
                      │
                      ▼
                  Response
                      │
                      ▼
                    USER
```

---

# 34. Example — Complex Task

User:

```text
Install Python, configure VS Code,
clone my project, read the README,
explain it, and run the project.
```

Architecture:

```text
User
 ↓
Query Router
 ↓
LangGraph
 ↓
Create Plan
 ↓
Resource Manager
 ↓
Check Resources
 ↓
AI Guardian
 ↓
Execute Step 1
 ↓
Verify
 ↓
Execute Step 2
 ↓
Verify
 ↓
Execute Step 3
 ↓
Verify
 ↓
Retrieve README
 ↓
LlamaIndex / Knowledge Layer
 ↓
Qwen
 ↓
Explain
 ↓
Run Project
 ↓
Verify
 ↓
Log
 ↓
Result
```

The system should not blindly load every capability at once.

---

# 35. Example — Screenshot Error

User:

```text
Read this screenshot and explain the error.
```

Architecture:

```text
User
 ↓
Query Router
 ↓
LangGraph
 ↓
Resource Manager
 ↓
Load:
OpenCV
EasyOCR
Qwen
 ↓
Process Screenshot
 ↓
Extract Text
 ↓
Reason About Error
 ↓
Response
 ↓
Release Vision Resources
 ↓
Log
```

---

# 36. Example — Hardware Check

User:

```text
Is my laptop compatible with this project?
```

Architecture:

```text
User
 ↓
Query Router
 ↓
LangGraph
 ↓
Resource Manager
 ↓
Load System Monitor
 ↓
psutil
 ↓
Collect:
CPU
RAM
Storage
Processes
 ↓
Compare Requirements
 ↓
Qwen
 ↓
Generate Explanation
 ↓
Release Unneeded Resources
 ↓
Log
 ↓
Response
```

---

# 37. Failure Handling

Every major component should have an error path.

```text
Request
 ↓
Plan
 ↓
Resource Check
 ↓
Execution
 ↓
Failure?
 ┌───────┴───────┐
 NO              YES
 ↓                ↓
Verify       Error Handler
 ↓                ↓
Success       Retry / Stop
 ↓                ↓
Log           Explain Error
```

The system should never report successful completion without appropriate verification.

---

# 38. Architecture Principles

Vault AI follows these principles:

### Modular

Each capability should be separated into an appropriate module.

### Resource-Aware

Only required capabilities should be loaded when possible.

### Local-First

Local AI should be preferred where practical.

### Safe

Sensitive operations should pass through policy and permission controls.

### Observable

Important actions should be logged and verifiable.

### Extensible

New functional modules should be capable of being added without redesigning the entire system.

### Maintainable

The architecture should separate UI, orchestration, reasoning, execution, data, and system operations.

---

# 39. Technology Mapping

| Architecture Component | Technology                    |
| ---------------------- | ----------------------------- |
| Desktop UI             | PySide6                       |
| Voice Input            | Faster-Whisper                |
| Voice Output           | Piper                         |
| Intent / Workflow      | LangGraph                     |
| Local AI               | Ollama + Qwen                 |
| Cloud AI               | OpenRouter                    |
| RAG                    | LlamaIndex                    |
| Vector Database        | ChromaDB                      |
| Embeddings             | BGE                           |
| Structured Database    | SQLite                        |
| System Monitoring      | psutil                        |
| Process Execution      | subprocess                    |
| Browser Automation     | Playwright                    |
| Computer Vision        | OpenCV                        |
| OCR                    | EasyOCR                       |
| API Layer              | FastAPI                       |
| Security               | Defender API / Sigma / Docker |
| Resource Optimization  | Dynamic Resource Manager      |
| Safety                 | AI Guardian                   |
| Execution              | Tool / Execution Manager      |

---

# 40. Architecture Summary

The core Vault AI architecture is:

```text
USER
 ↓
PYSide6
 ↓
QUERY / INTENT ROUTER
 ↓
LANGGRAPH
 ↓
┌─────────────────────────────────┐
│                                 │
│ AI MODEL MANAGER                │
│ RESOURCE MANAGER                │
│ AI GUARDIAN                     │
│                                 │
└────────────────┬────────────────┘
                 ↓
        TOOL / EXECUTION MANAGER
                 ↓
        FUNCTIONAL MODULES
                 ↓
          OPERATING SYSTEM
                 ↓
             HARDWARE
```

Supporting the architecture:

```text
                 ┌───────────────┐
                 │     DATA      │
                 │               │
                 │ SQLite        │
                 │ ChromaDB      │
                 │ LlamaIndex    │
                 │ BGE           │
                 │ Memory        │
                 │ Logs          │
                 └───────────────┘
```

The most important architectural idea is that **LangGraph controls the workflow, the Resource Manager controls resource usage, the AI Model Manager controls model selection, the AI Guardian controls safety, and the Execution Manager controls actual system actions.**

This separation prevents the LLM from becoming an unrestricted controller of the operating system.
