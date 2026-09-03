# Vault AI — Product Requirements Document

**Project:** Vault AI
**Document:** Product Requirements Document
**Version:** 1.0
**Status:** MVP Development
**Target:** Offline / Local-First AI Desktop Agent

---

# 1. Product Overview

Vault AI is an AI-powered desktop agent designed to allow users to interact with their computer through natural-language commands.

The system combines a desktop interface, local and cloud AI models, AI orchestration, dynamic resource management, system tools, automation modules, memory, security controls, and verification.

The primary objective is not to load every capability at the same time. Instead, Vault AI should dynamically determine which capabilities are required for the current task and load only the necessary resources.

The core principle is:

```text
Understand
    ↓
Plan
    ↓
Check Resources
    ↓
Load Required Capability
    ↓
Ask Permission if Required
    ↓
Execute
    ↓
Verify
    ↓
Log
    ↓
Unload Unused Resources
    ↓
Respond
```

---

# 2. Problem Statement

A traditional desktop requires users to manually interact with multiple applications, system utilities, files, browsers, and configuration tools.

An AI desktop agent can simplify this interaction by allowing the user to express an intended task in natural language.

However, an AI desktop agent introduces another major problem:

> Advanced AI capabilities can consume significant CPU, RAM, GPU, and other system resources when loaded simultaneously.

For example, a task may require:

```text
Qwen
OpenCV
EasyOCR
Playwright
Whisper
Docker
```

but loading all of these at once can unnecessarily consume system resources.

Vault AI therefore introduces a **Dynamic Resource Manager** responsible for determining which resources and modules are required for the current task.

---

# 3. Product Vision

Vault AI aims to become a local-first intelligent desktop agent that can:

* Understand natural-language commands.
* Plan multi-step tasks.
* Select appropriate AI models.
* Dynamically load required capabilities.
* Monitor hardware resources.
* Execute desktop operations.
* Request permission for sensitive operations.
* Use local AI whenever practical.
* Use cloud AI when required or beneficial.
* Verify completed actions.
* Maintain memory and logs.
* Protect the user's system.

---

# 4. Core Design Principles

## 4.1 Local-First

Vault AI should prefer local processing whenever the required capability can reasonably be provided locally.

The local AI stack includes:

```text
Ollama
   ↓
Qwen
```

---

## 4.2 Dynamic Resource Usage

Vault AI should not load every available module at startup.

Instead:

```text
Task
 ↓
Required Capabilities
 ↓
Resource Check
 ↓
Load Required Modules
 ↓
Execute
 ↓
Unload When No Longer Required
```

This approach is referred to as dynamic or lazy loading.

---

## 4.3 Planned Execution

Complex requests should first be converted into a plan.

Example:

```text
User:

Setup Python for VS Code,
open this file,
attach it to the project,
and check whether my hardware is compatible.
```

Vault AI should produce a plan similar to:

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

The system should not blindly execute every operation simultaneously.

---

## 4.4 Controlled Execution

The AI should not directly control the operating system.

Instead:

```text
AI
 ↓
Tool Selection
 ↓
Guardian / Policy Check
 ↓
Execution Manager
 ↓
Tool
 ↓
Operating System
```

---

## 4.5 Verification

After execution, Vault AI should verify whether the requested operation actually succeeded.

```text
Execute
   ↓
Verify
   ↓
Success / Failure
   ↓
Log
```

---

# 5. Target Users

The primary target user is a desktop computer user who wants to perform system, application, file, automation, and information tasks using natural-language commands.

The MVP is also intended to demonstrate the architecture and feasibility of an AI desktop agent as a major software project.

---

# 6. MVP Goals

The first working version should demonstrate the following capabilities:

### AI

* Local LLM integration.
* Cloud LLM fallback/integration.
* Natural-language understanding.
* Task planning.
* Tool selection.

### Desktop

* Application launching.
* File management.
* System monitoring.
* Browser automation.
* Selected desktop automation.

### Resource Management

* CPU monitoring.
* RAM monitoring.
* GPU availability checking where supported.
* Dynamic module loading.
* Dynamic module unloading.
* Task scheduling.
* Resource-aware execution.

### Safety

* Permission checking.
* AI Guardian.
* Controlled execution.
* Audit logging.
* Verification.

### Knowledge

* Document indexing.
* Retrieval.
* Vector search.
* Context-aware responses.

---

# 7. Functional Requirements

## FR-01 — Natural Language Input

The system shall allow the user to enter natural-language commands through the desktop interface.

---

## FR-02 — AI Orchestration

The system shall use an orchestration layer to determine the sequence of operations required to complete a task.

The planned orchestration technology is:

```text
LangGraph
```

---

## FR-03 — Local AI

The system shall support local AI inference using:

```text
Ollama
+
Qwen
```

---

## FR-04 — Cloud AI

The system shall support cloud AI through:

```text
OpenRouter
```

The system may route suitable tasks to cloud models when local execution is insufficient or when the architecture determines that cloud reasoning is appropriate.

---

## FR-05 — Model Selection

Vault AI shall contain an AI Model Manager responsible for selecting the appropriate AI model or provider.

Conceptually:

```text
Request
   ↓
AI Model Manager
   ↓
Local Qwen OR Cloud Model
```

---

## FR-06 — Resource Management

The system shall contain a Dynamic Resource Manager.

It shall be responsible for:

* Checking available RAM.
* Monitoring CPU load.
* Checking GPU availability where applicable.
* Determining required modules.
* Loading required modules.
* Unloading modules that are no longer required.
* Scheduling resource-intensive tasks.
* Preventing unnecessary simultaneous execution.

---

## FR-07 — File Operations

The system shall support controlled file operations.

Potential operations include:

* List files.
* Copy files.
* Move files.
* Delete files.
* Organize files.

---

## FR-08 — System Monitoring

The system shall monitor system resources using the system-monitoring layer.

The planned Python technology is:

```text
psutil
```

Potential monitored resources include:

* CPU
* RAM
* Storage
* Processes
* Network/system information where supported

---

## FR-09 — Application Automation

Vault AI shall support controlled launching and interaction with desktop applications.

The planned Python mechanism includes:

```text
subprocess
```

---

## FR-10 — Browser Automation

The system shall support browser automation through:

```text
Playwright
```

when a task specifically requires browser interaction.

Playwright should not be loaded for tasks that do not require browser automation.

---

## FR-11 — Vision

For tasks requiring screen/image understanding, Vault AI may dynamically load:

```text
OpenCV
EasyOCR
```

Example:

```text
User:
Read this screenshot and explain the error.
```

Required resources may become:

```text
OpenCV
EasyOCR
Qwen
```

Unrelated modules such as Whisper, Piper, Docker, or Playwright should not be loaded unless separately required.

---

## FR-12 — Voice Input

The planned voice-input technology is:

```text
Faster-Whisper
```

It should be loaded only when voice input is required.

---

## FR-13 — Voice Output

The planned text-to-speech technology is:

```text
Piper
```

It should be loaded only when voice output is required.

---

## FR-14 — Retrieval-Augmented Generation

Vault AI shall support document retrieval and contextual knowledge processing.

The planned stack includes:

```text
LlamaIndex
     ↓
ChromaDB
     ↓
BGE Embeddings
```

---

## FR-15 — Memory

Vault AI shall maintain appropriate memory and history for tasks and user interaction.

The detailed memory architecture will be defined separately in:

```text
MEMORY.md
```

---

## FR-16 — Permission Management

The system shall identify operations that require user permission.

Sensitive operations should follow:

```text
Request
 ↓
Plan
 ↓
Risk Check
 ↓
Permission
 ↓
Execute
```

---

## FR-17 — AI Guardian

The AI Guardian shall provide a safety and policy-control layer before sensitive operations are executed.

It should help prevent unintended or unauthorized actions.

---

## FR-18 — Execution Manager

The Execution Manager shall be responsible for controlled interaction with system tools and functional modules.

The AI should select an action, but the execution layer should control how that action is actually performed.

---

## FR-19 — Verification

Vault AI shall verify important operations after execution.

Example:

```text
Install Python
     ↓
Verify Python installation
     ↓
Continue
```

If verification fails, the system should report the failure rather than assuming success.

---

## FR-20 — Logging

The system shall maintain logs containing appropriate task information such as:

* User request.
* Selected action.
* Execution status.
* Permission status.
* Result.
* Timestamp.
* Relevant errors.

---

# 8. Technology Stack

## User Interface

```text
PySide6
```

Used for the desktop GUI.

---

## Orchestration

```text
LangGraph
```

Used to manage multi-step AI workflows and task execution flow.

---

## Local AI

```text
Ollama
Qwen
```

Used for local model inference.

---

## Cloud AI

```text
OpenRouter
```

Used as the cloud-model integration layer.

---

## RAG / Knowledge

```text
LlamaIndex
ChromaDB
BGE Embeddings
```

Used for document indexing, retrieval, vector storage, and semantic search.

---

## Database

```text
SQLite
```

Used for structured local application data.

---

## System Monitoring

```text
psutil
```

Used to monitor system resources and processes.

---

## Desktop Execution

```text
subprocess
```

Used for controlled operating-system/application execution.

---

## Browser Automation

```text
Playwright
```

Used only when browser automation is required.

---

## Computer Vision

```text
OpenCV
EasyOCR
```

Used for image and screen understanding when required.

---

## Voice

```text
Faster-Whisper
Piper
```

Used for speech recognition and voice output.

---

## API Layer

```text
FastAPI
```

Used for the relevant API/backend integration layer.

---

## Security

The planned security-related technologies include:

```text
Windows Defender API
Sigma
Docker
```

These components are intended to support system-security and isolation capabilities.

---

# 9. Dynamic Resource Manager

The Dynamic Resource Manager is a key component of Vault AI.

Its responsibilities include:

```text
Resource Manager
│
├── Check RAM
├── Check CPU
├── Check GPU
├── Determine required modules
├── Load modules
├── Unload modules
├── Schedule tasks
├── Prevent resource conflicts
└── Select execution strategy
```

Example:

```text
User Request
      ↓
LangGraph
      ↓
Resource Manager
      │
      ├── RAM enough?
      ├── CPU available?
      ├── GPU available?
      ├── Which modules are required?
      ├── Load required modules
      ├── Schedule task
      └── Unload unused modules
```

The Resource Manager is intended to allow Vault AI to operate more efficiently on ordinary consumer hardware.

---

# 10. Sequential Task Execution

A large task should normally be broken into manageable steps.

Example:

```text
User Request
     ↓
Create Plan
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
Clone Repository
     ↓
Read README
     ↓
Explain README
     ↓
Run Project
     ↓
Verify Result
     ↓
Done
```

Independent operations may be executed in parallel only when the Resource Manager determines that doing so is safe and beneficial.

---

# 11. Dynamic Module Loading

Vault AI should avoid loading every capability into memory.

### Example 1 — Hardware Check

Required:

```text
psutil
```

After completion:

```text
psutil
→ no longer required
→ unload/release resources where applicable
```

### Example 2 — Python Check

Required:

```text
subprocess
```

### Example 3 — Screenshot Understanding

Required:

```text
OpenCV
EasyOCR
Qwen
```

Unnecessary modules should remain unloaded.

---

# 12. Resource-Aware Model Selection

If the system detects insufficient resources, the Resource Manager and AI Model Manager may adjust execution strategy.

Possible strategies include:

```text
Use smaller local model
        OR
Use cloud model through OpenRouter
        OR
Queue the task
        OR
Ask user to free resources
```

The exact routing policy will be defined in the architecture and rules documents.

---

# 13. Security Requirements

Vault AI shall use controlled execution rather than unrestricted AI-generated system commands.

Sensitive actions should pass through:

```text
AI
 ↓
AI Guardian
 ↓
Permission
 ↓
Execution Manager
 ↓
Tool
```

Security-related operations should also be logged and verified where appropriate.

---

# 14. Data Requirements

The application may maintain local structured data for:

* User information.
* Settings.
* Task history.
* Execution logs.
* Permissions.
* Memory metadata.
* Application configuration.

SQLite is the planned structured database.

Knowledge/document retrieval may use ChromaDB and the associated retrieval stack.

---

# 15. User Interface Requirements

The desktop application should provide major areas for:

```text
Login
Dashboard
Chat
System Monitor
Task History
Settings
```

The detailed visual and interaction design will be defined in:

```text
DESIGN.md
```

---

# 16. Error Handling

Vault AI should not assume that an action succeeded simply because a tool was called.

The execution pipeline should support:

```text
Execute
   ↓
Check Result
   ↓
Success?
 /     \
Yes     No
 ↓       ↓
Log     Error Handling
 ↓       ↓
Continue Retry / Report
```

---

# 17. Performance Requirements

The application should minimize unnecessary resource usage.

The system should:

* Avoid loading unused modules.
* Avoid unnecessary parallel execution.
* Monitor resource availability.
* Prefer appropriate local models when possible.
* Release resources when capabilities are no longer required.
* Schedule expensive operations when necessary.

---

# 18. Privacy Requirements

Vault AI should favor local processing where practical.

The architecture should clearly distinguish between:

```text
Local Processing
```

and:

```text
Cloud Processing
```

before sending information to an external model/provider.

---

# 19. MVP Success Criteria

The MVP will be successful if it demonstrates a complete controlled agent workflow:

```text
User
 ↓
Natural Language
 ↓
Intent / Query Router
 ↓
LangGraph
 ↓
AI Model Manager
 ↓
Resource Manager
 ↓
AI Guardian
 ↓
Execution Manager
 ↓
Functional Module
 ↓
Operating System
 ↓
Verification
 ↓
Logging
 ↓
User Result
```

The system should demonstrate this flow reliably for selected desktop tasks.

---

# 20. Future Scope

The project may later expand toward:

* More autonomous task planning.
* More advanced multi-agent orchestration.
* Additional plugins.
* More desktop integrations.
* Advanced cybersecurity capabilities.
* Expanded RAG capabilities.
* Additional local and cloud models.
* Cross-platform support.
* More sophisticated resource scheduling.

These should not be allowed to compromise the stability of the MVP.

---

# 21. Product Principle

The central product principle of Vault AI is:

```text
Understand
    ↓
Plan
    ↓
Check
    ↓
Load
    ↓
Protect
    ↓
Execute
    ↓
Verify
    ↓
Log
    ↓
Release
    ↓
Respond
```

Vault AI is therefore not simply a chatbot.

It is intended to be a **resource-aware, safety-controlled, AI-powered desktop agent**.
