# Vault AI — System Rules

**Project:** Vault AI
**Document:** System Rules
**Version:** 1.0
**Status:** Specification
**Purpose:** Define the behavioral, safety, resource, execution, and AI rules of Vault AI.

---

# 1. Purpose

This document defines the rules that Vault AI must follow when interpreting, planning, executing, verifying, and recording user requests.

These rules apply to the planned Vault AI architecture.

They are specifications for the system and do not imply that every component is currently implemented.

---

# 2. Core Agent Rule

Vault AI should follow this general lifecycle:

```text
USER REQUEST
     ↓
UNDERSTAND
     ↓
CLASSIFY
     ↓
PLAN
     ↓
CHECK
     ↓
GET APPROVAL IF REQUIRED
     ↓
CHECK RESOURCES
     ↓
LOAD REQUIRED MODULES
     ↓
EXECUTE
     ↓
VERIFY
     ↓
LOG
     ↓
RELEASE UNUSED RESOURCES
     ↓
RESPOND
```

The agent must not treat every request as an unrestricted command.

---

# 3. User Intent Classification Rule

Every incoming request should first be classified by the Query / Intent Router.

The architecture defines the following primary paths:

```text
A. Casual Chat
B. Simple Task
C. Information / Q&A
D. Action / System Task
E. Installation / Change
F. Complex / Multi-Step
```

---

# 4. Casual Chat Rule

Casual conversation should use the shortest suitable path.

Example:

```text
User:
Hello
```

Expected path:

```text
User
 ↓
Intent Router
 ↓
Casual Chat
 ↓
Qwen / Local AI
 ↓
Response
```

A full LangGraph workflow should not be required for ordinary casual conversation.

---

# 5. Simple Task Rule

Simple, low-risk tasks should use a quick local path when possible.

Examples:

```text
Show CPU usage.
Open VS Code.
```

Possible path:

```text
User
 ↓
Router
 ↓
Simple Task
 ↓
Quick Tool
 ↓
Local Execution
 ↓
Result
```

Examples of suitable tools include:

```text
psutil
subprocess
file operations
```

---

# 6. Information / Q&A Rule

Information requests should use the appropriate knowledge path.

For local knowledge or indexed information:

```text
LlamaIndex
+
ChromaDB
+
BGE Embeddings
```

For current online information, the system may use an optional web layer.

Conceptually:

```text
Question
 ↓
Router
 ↓
Information / Q&A
 ↓
RAG / Web Layer
 ↓
AI Model
 ↓
Response
```

---

# 7. Action / System Task Rule

System-changing or application actions should not be treated like ordinary conversation.

Examples:

```text
Create a file.
Open an application.
Move files.
Run a system operation.
```

These should use an appropriate tool and execution path.

---

# 8. Installation / Change Rule

Installation or system-changing requests must use the full validation path.

Examples:

```text
Install Python.
Install a package.
Update a driver.
Change a system configuration.
```

The expected flow is:

```text
Request
 ↓
Plan
 ↓
AI Guardian
 ↓
Safety Checks
 ↓
User Approval if required
 ↓
Resource Check
 ↓
Execution
 ↓
Verification
 ↓
Log
```

---

# 9. Complex Task Rule

Complex or multi-step tasks should use the agentic workflow.

Example:

```text
Setup my complete development environment.
```

Expected architecture:

```text
User
 ↓
Router
 ↓
LangGraph
 ↓
Planner
 ↓
Reasoning
 ↓
Task Manager
 ↓
AI Guardian
 ↓
Approval
 ↓
Resource Manager
 ↓
Tools
 ↓
Verification
 ↓
Logging
```

---

# 10. Planning Rule

The agent must create a plan before executing a complex task.

Example:

```text
User:

Setup Python for VS Code,
open this file,
attach it to the project,
and check my hardware.
```

The planner may produce:

```text
1. Check hardware.
2. Check Python installation.
3. Install Python if required.
4. Install required VS Code components.
5. Open VS Code.
6. Open project folder.
7. Open requested file.
8. Verify configuration.
```

The plan should exist before execution begins.

---

# 11. Dependency Rule

If Task B depends on Task A, Task B must not begin until Task A has completed successfully or has produced an acceptable result.

Example:

```text
Install Python
      ↓
Verify Python
      ↓
Configure Python
```

The system must not configure Python before confirming that Python is available.

---

# 12. Sequential Execution Rule

The default behavior for dependent tasks is sequential execution.

```text
Step 1
 ↓
Finish
 ↓
Verify
 ↓
Step 2
 ↓
Finish
 ↓
Verify
```

This prevents later actions from operating on incomplete or invalid state.

---

# 13. Parallel Execution Rule

Independent tasks may run in parallel only when all of the following are true:

1. They do not depend on each other.
2. Running them simultaneously will not create a conflict.
3. The Resource Manager determines that sufficient resources are available.
4. The AI Guardian does not prohibit parallel execution.
5. The operations can be independently verified.

Otherwise, they must execute sequentially.

---

# 14. Resource Manager Rule

The Dynamic Resource Manager must act as the resource-control layer.

Its responsibilities include:

```text
Monitor resources
 ↓
Determine requirements
 ↓
Select modules
 ↓
Load required modules
 ↓
Control task scheduling
 ↓
Optimize resource usage
 ↓
Release unused resources
```

The architecture identifies this component as a major innovation of Vault AI.

---

# 15. Resource Monitoring Rule

The Resource Manager should consider available system resources such as:

```text
CPU
RAM
Disk / Storage
GPU
Battery
```

The planned monitoring stack includes:

```text
psutil
```

where supported by the implementation.

---

# 16. Resource Availability Rule

Before starting a resource-intensive task, Vault AI should determine whether the system has sufficient resources.

Conceptually:

```text
Task
 ↓
Required Resources
 ↓
Available Resources
 ↓
Enough?
```

If enough:

```text
Continue
```

If insufficient:

```text
Reduce Load
OR
Queue Task
OR
Use Alternative Model
OR
Ask User
```

---

# 17. Lazy Loading Rule

Vault AI must not load every available capability simply because the capability exists.

It should load only the modules required for the current task.

Example:

```text
Task:
Check hardware
```

Required:

```text
psutil
```

Not required:

```text
OpenCV
EasyOCR
Playwright
Whisper
Piper
Docker
```

---

# 18. Module Unloading Rule

When a dynamically loaded capability is no longer required, Vault AI should release or unload it where technically possible.

Conceptually:

```text
Load
 ↓
Use
 ↓
Verify
 ↓
Release
```

The system should not retain expensive resources indefinitely without a reason.

---

# 19. Shared Module Rule

If multiple active tasks require the same module, the Resource Manager should avoid unnecessary duplicate loading.

Example:

```text
Task A → Qwen
Task B → Qwen
```

The system should reuse the active compatible resource when safe instead of creating unnecessary duplicate instances.

---

# 20. Resource Conflict Rule

If two tasks compete for limited resources, the Resource Manager should decide whether to:

```text
Run sequentially
Run partially in parallel
Queue one task
Use an alternative resource
Reduce model/resource requirements
```

The system must prioritize system stability over unnecessary parallelism.

---

# 21. Local-First AI Rule

Vault AI should prefer local AI processing when the task can reasonably be completed locally.

The planned local stack is:

```text
Ollama
 ↓
Qwen
```

This supports the offline-first design.

---

# 22. Cloud AI Rule

Cloud AI should be used when:

* The task requires capabilities unavailable locally.
* Local resources are insufficient.
* The configured routing policy determines that cloud reasoning is appropriate.
* The user has permitted the relevant cloud usage where required.

The planned cloud integration is:

```text
OpenRouter
```

---

# 23. Privacy Routing Rule

Before sending information to a cloud model, Vault AI should consider whether the task contains information that should remain local.

Conceptually:

```text
Request
 ↓
Privacy Check
 ↓
Can process locally?
 ├── Yes → Local AI
 └── No / unsuitable → Cloud path if permitted
```

Sensitive information should not be unnecessarily sent to external services.

---

# 24. Model Selection Rule

The AI Model Manager should consider:

```text
Task type
Privacy requirements
Model capability
RAM
CPU
GPU
Model availability
Internet availability
Latency
```

Possible result:

```text
Local Qwen
OR
OpenRouter model
```

The Model Manager should not select a model without considering the relevant task and system state.

---

# 25. AI Guardian Rule

The AI Guardian is the validation and safety layer.

It should inspect proposed operations before sensitive execution.

The architecture identifies checks including:

```text
Security Check
OS Compatibility Check
Dependency Check
Hardware Compatibility Check
Resource Check
Risk / Impact Analysis
```

---

# 26. Security Check Rule

Operations with security implications should be checked before execution.

The planned security technologies include:

```text
Defender API
Sigma Rules
Docker
```

The exact implementation will depend on the supported operating system and security capabilities.

---

# 27. OS Compatibility Rule

Before performing an OS-specific action, Vault AI should determine whether the requested operation is compatible with the current environment.

Example:

```text
Requested operation
 ↓
Current OS
 ↓
Compatibility Check
 ↓
Compatible?
```

If incompatible, the system should not blindly execute the operation.

---

# 28. Dependency Check Rule

Before executing an action that requires a dependency:

```text
Check dependency
 ↓
Available?
```

If available:

```text
Continue
```

If unavailable:

```text
Install / Configure
OR
Ask User
OR
Suggest Alternative
```

Installation or modification must follow the appropriate safety rules.

---

# 29. Hardware Compatibility Rule

Before resource-intensive or hardware-dependent operations, Vault AI should determine whether the available hardware is suitable.

Potential factors include:

```text
CPU
RAM
GPU
Storage
Battery / Power
```

---

# 30. Risk Analysis Rule

The AI Guardian should evaluate the potential impact of an operation.

Risk may depend on:

```text
Data modification
System modification
Security impact
Reversibility
Required privileges
External communication
Resource consumption
```

Higher-impact operations should receive stronger validation.

---

# 31. Permission Rule

Sensitive actions should require explicit user approval.

The approval interface should provide an action preview containing information such as:

```text
What will happen?
Why is it required?
What is the expected impact?
```

The user should be able to:

```text
Approve
OR
Cancel
```

---

# 32. No Approval, No Execution Rule

If an operation requires explicit approval and the user has not approved it:

```text
DO NOT EXECUTE
```

The system should instead:

```text
Wait
OR
Cancel
OR
Return to user
```

---

# 33. Rejection Rule

If the AI Guardian determines that an action is unsafe or unacceptable:

```text
Reject
 ↓
Do not execute
 ↓
Inform User
 ↓
Explain Risk
 ↓
Suggest Alternative where possible
```

The system should never bypass the Guardian to force execution.

---

# 34. Execution Manager Rule

The AI should not directly execute arbitrary operating-system commands.

The expected separation is:

```text
AI
 ↓
Tool Selection
 ↓
AI Guardian
 ↓
Execution Manager
 ↓
Approved Tool
 ↓
Operating System
```

The Execution Manager provides the controlled execution boundary.

---

# 35. Tool Selection Rule

Only the tools necessary for the current operation should be selected.

Examples:

```text
CPU monitoring
→ psutil

Application launch
→ subprocess

Browser task
→ Playwright

Screenshot OCR
→ OpenCV + EasyOCR

Voice input
→ Faster-Whisper
```

Unnecessary tools should not be loaded.

---

# 36. File Operation Rule

File operations should use controlled filesystem functionality.

Potential tools include:

```text
pathlib
shutil
```

File modification operations should be treated more cautiously than read-only operations.

---

# 37. Destructive Action Rule

Actions that can cause irreversible or significant data loss should receive appropriate validation and user approval.

Examples:

```text
Delete files
Delete folders
Overwrite important files
Bulk modification
```

The system should clearly show what is going to be affected before execution where practical.

---

# 38. Browser Automation Rule

Playwright should only be loaded when browser automation is required.

Example:

```text
Browser task
 ↓
Resource Manager
 ↓
Load Playwright
 ↓
Browser operation
 ↓
Verify
 ↓
Release when no longer required
```

---

# 39. Vision Rule

OpenCV and EasyOCR should only be loaded when image/screen analysis requires them.

Example:

```text
Screenshot
 ↓
OpenCV
 ↓
EasyOCR
 ↓
Qwen
 ↓
Explanation
```

---

# 40. Voice Rule

Voice processing should be loaded only when voice interaction is required.

Input:

```text
Faster-Whisper
```

Output:

```text
Piper
```

The system should not load voice models for ordinary text-only interaction.

---

# 41. RAG Rule

When indexed knowledge is required, Vault AI should use the retrieval layer.

Planned components:

```text
LlamaIndex
ChromaDB
BGE Embeddings
```

The system should retrieve relevant information rather than unnecessarily processing the entire knowledge base.

---

# 42. Memory Rule

Memory should be used only when relevant to the current task and according to the defined memory policy.

Memory should not become an unrestricted source of context.

The detailed memory policy is defined separately in:

```text
MEMORY.md
```

---

# 43. Verification Rule

Important actions must be verified after execution.

Example:

```text
Install Python
 ↓
Run installation
 ↓
Check Python version
 ↓
Verification
```

The system must not assume success merely because the execution command returned.

---

# 44. Failure Rule

If verification fails:

```text
Execution
 ↓
Verification
 ↓
Failure
```

The system should:

```text
Stop dependent tasks
 ↓
Record failure
 ↓
Explain failure
 ↓
Retry only when safe and appropriate
OR
Suggest alternative
```

---

# 45. Retry Rule

Retries must not be unlimited.

A retry should occur only when:

* The operation is safe to retry.
* The cause of failure is understood or reasonably recoverable.
* Repeating the action will not create harmful side effects.

Destructive operations should not be blindly retried.

---

# 46. Logging Rule

Important operations should generate an audit record.

A log may contain:

```text
Timestamp
User Request
Intent
Plan
Selected Model
Selected Tools
Permission Decision
Execution Result
Verification Result
Error
```

---

# 47. Transparency Rule

For important operations, Vault AI should be able to explain:

```text
What it is doing
Why it is doing it
Which capability it is using
Whether approval is required
Whether the operation succeeded
```

The explanation should be understandable to the user.

---

# 48. No False Success Rule

Vault AI must never claim that an operation succeeded without appropriate evidence.

Incorrect:

```text
Python installed successfully.
```

when installation has not been verified.

Correct behavior:

```text
Python installation completed.
Verification:
Python 3.x detected.

Status:
Success.
```

---

# 49. Resource Failure Rule

If resources are insufficient, the system should not simply continue and overload the machine.

It may:

```text
Reduce concurrency
Queue the task
Use a smaller model
Use cloud intelligence if permitted
Release unused modules
Ask the user to free resources
```

---

# 50. System Stability Rule

System stability has priority over maximum parallel execution.

The system should prefer:

```text
Safe + stable execution
```

over:

```text
Maximum simultaneous execution
```

---

# 51. Offline-First Rule

Vault AI should remain useful without an internet connection for capabilities that can operate locally.

Example:

```text
Offline
 ↓
Local Qwen
 ↓
Local Tools
 ↓
Local Data
```

Cloud-dependent functionality should fail gracefully when internet access is unavailable.

---

# 52. Cloud Failure Rule

If OpenRouter or another cloud service is unavailable:

```text
Cloud Request
 ↓
Failure
```

Vault AI should, where possible:

```text
Use local model
OR
Use a local tool
OR
Explain that the capability is unavailable
```

It should not silently pretend that the cloud operation succeeded.

---

# 53. Module Isolation Rule

Functional modules should have clear responsibilities.

Examples:

```text
Monitoring
→ System resource information

Browser
→ Browser automation

Vision
→ Image / OCR processing

Speech
→ Voice processing

Security
→ Security-related operations
```

One module should not unnecessarily control unrelated functionality.

---

# 54. Extensibility Rule

The architecture should allow new functional modules to be added without redesigning the complete system.

New modules should integrate through controlled interfaces with:

```text
Resource Manager
Tool / Execution Manager
AI Guardian
Logging
Verification
```

---

# 55. Plugin Rule

Future custom plugins should not automatically receive unrestricted system access.

A plugin should be subject to the same relevant:

```text
Resource rules
Security rules
Permission rules
Execution rules
Verification rules
Logging rules
```

---

# 56. Authentication Rule

Vault AI authentication and device-security mechanisms remain part of the existing security foundation.

The current project already contains authentication and device-security functionality.

New AI capabilities must not bypass the application's authentication boundary.

---

# 57. Data Protection Rule

Application data, credentials, memory, and logs should be protected according to their sensitivity.

The AI should not expose protected information merely because a user asks an unrelated question.

---

# 58. Command Injection Protection Rule

AI-generated tool arguments must be treated as untrusted input.

The Execution Manager should validate tool parameters before passing them to:

```text
subprocess
shell
filesystem
browser
APIs
```

The LLM should never be considered a trusted security boundary.

---

# 59. Least-Privilege Rule

A tool should receive only the permissions necessary to perform its task.

Example:

```text
Read file
```

should not automatically imply:

```text
Delete file
```

Similarly:

```text
Open application
```

should not automatically imply unrestricted system modification.

---

# 60. Human Control Rule

The user remains the final authority for operations that require explicit approval.

Vault AI may:

```text
Analyze
Plan
Recommend
Validate
```

but must wait for user approval when the rules require it.

---

# 61. Resource Manager + Guardian Interaction

The Resource Manager and AI Guardian should exchange relevant information.

Example:

```text
AI Guardian
    ↕
Resource Manager
```

The Guardian may need resource information to assess whether an operation is safe.

The Resource Manager may need Guardian decisions before scheduling sensitive tasks.

---

# 62. LangGraph + Guardian Interaction

LangGraph controls the workflow, but it must not bypass safety controls.

Correct:

```text
LangGraph
 ↓
Plan
 ↓
Guardian
 ↓
Approval
 ↓
Resource Manager
 ↓
Execution
```

Incorrect:

```text
LangGraph
 ↓
Direct unrestricted execution
```

---

# 63. LangGraph + Resource Manager Interaction

LangGraph may determine what tasks need to happen.

The Resource Manager determines how those tasks should be scheduled based on available resources.

Therefore:

```text
LangGraph
→ What needs to happen?

Resource Manager
→ When/how should it run given resources?
```

---

# 64. Resource Manager + Module Lifecycle

The Resource Manager should control:

```text
Module Requested
 ↓
Resource Check
 ↓
Load
 ↓
Use
 ↓
Verify
 ↓
Release
```

This is a central rule of the resource-aware architecture.

---

# 65. Complete Safety Pipeline

For a sensitive operation:

```text
User Request
 ↓
Intent Router
 ↓
LangGraph / Planner
 ↓
AI Model Manager
 ↓
AI Guardian
 ├── Security Check
 ├── OS Check
 ├── Dependency Check
 ├── Hardware Check
 ├── Resource Check
 └── Risk Analysis
 ↓
Safe?
 ├── NO
 │    ↓
 │  Reject
 │    ↓
 │  Explain / Alternative
 │
 └── YES
      ↓
 User Approval if required
      ↓
 Resource Manager
      ↓
 Load Required Modules
      ↓
 Execution Manager
      ↓
 Execute
      ↓
 Verify
      ↓
 Log
      ↓
 Release Resources
      ↓
 Respond
```

---

# 66. Rule Priority

When multiple rules apply, the following priority should generally be followed:

```text
1. Safety
2. User approval
3. Security
4. Resource availability
5. Task dependencies
6. Correct execution
7. Performance optimization
```

Performance optimization must never override a safety requirement.

---

# 67. Final Rule

Vault AI should never be designed as:

```text
User
 ↓
LLM
 ↓
Execute Anything
```

It should operate as:

```text
User
 ↓
Understand
 ↓
Plan
 ↓
Validate
 ↓
Check Resources
 ↓
Approve
 ↓
Load Required Capability
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

This rule defines the fundamental safety and resource-management philosophy of Vault AI.
