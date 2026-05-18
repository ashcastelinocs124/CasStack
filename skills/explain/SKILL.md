# Explain Skill
**Description:** Explain codebase concepts, architecture, and implementation details from first principles when users ask questions about how the system works.
**Usage:** /explain [topic] [optional: depth=basic]

**Trigger this skill when:**
- User asks "how does X work?", "what is Y?", "explain this"
- User wants to understand code architecture, design decisions, or implementation patterns
- User needs conceptual clarification with concrete examples
- User asks about specific functions, modules, or data flows

**Skip for:** Simple syntax questions, "what's the error?" (use LSP), obvious code that's self-documenting

## CORE PRINCIPLE — Explain from First Principles

**This is the single most important rule of this skill: derive understanding from fundamental constraints and problem requirements, not from summarizing what the code does.**

A non-first-principles explanation says: *"The service worker has a `repoCache` Map keyed by `owner/repo@branch` so re-opening the panel is instant."* — that's a description of what exists.

A first-principles explanation says: *"Chrome MV3 forbids the side panel from doing cross-origin fetches, so the crawl has to live in the service worker. But MV3 service workers get killed when idle — without a cache, every panel re-open would re-crawl the same repo and re-burn the user's GitHub rate budget. That forces an in-memory cache keyed by something stable across calls (owner + repo + branch), which is exactly what `repoCache` is."* — that's the **why this has to exist at all**.

### How to apply first principles

Before describing any component, ask and answer in your explanation:

1. **What is the underlying problem?** (Not "what does the code do" — what real-world constraint or requirement creates the need for code at all.)
2. **What are the inescapable constraints?** (Browser sandbox rules, network limits, latency budgets, language semantics, security boundaries, hardware limits, user expectations.)
3. **What is the minimum that must exist to satisfy (1) under (2)?** (This is the design — derive it, don't quote it.)
4. **Why couldn't a simpler approach work?** (Name the simpler approach that would seem natural, then explain which constraint kills it.)
5. **Only now**, point at the code that implements the derived design. The code becomes the *answer* to the derivation, not the starting point.

### Red flags that you've slipped into description-mode

If your explanation contains phrases like these, you have stopped reasoning from first principles and started summarizing the code. Rewrite the section:

| Bad (description) | Good (first principles) |
|---|---|
| "This function does X" | "X has to happen because [constraint]; the function is just where that lives" |
| "There's a Map called Y that stores Z" | "Z needs to survive across calls because [constraint], and the cheapest data structure that gives O(1) lookup by [key] is a Map — hence Y" |
| "Step 1, step 2, step 3..." | "The job decomposes into these steps because [constraint A] forces ordering and [constraint B] makes step N impossible to skip" |
| "It uses pattern X" | "Pattern X is the smallest abstraction that handles [requirement]; without it you'd need to [worse alternative]" |
| "The code does this for performance" | "The naive version costs O(N²) because [reason]; this version is O(N log N) because [trick], which matters once N > [threshold]" |

### When code exists *only* because of an arbitrary choice (no deeper principle)

Be honest about it. Say *"This is a convention, not a derivation — it could equally have been X."* Don't manufacture fake principles to justify accidental design.

## Execution Workflow

### Step 1: Parse User Query
**Identify the core question:**
- What system/component are they asking about?
- What level of detail do they need?
- Are they asking for high-level architecture or specific implementation?
- Any specific file/function mentioned?

**Classify question type:**
| Type | Signal | Approach |
|------|--------|---------|
| Architecture | "how does routing work?", "explain the system" | High-level overview + component interactions |
| Implementation | "how does X function work?", "why is this here?" | Specific code walkthrough |
| Data Flow | "what happens when user asks Y?" | Trace request/response path |
| Design Decision | "why did you use pattern X?" | Explain trade-offs and rationale |

### Step 2: Gather Context

**Default: use a code knowledge-graph MCP if one is available** (e.g. `code-review-graph`). Graphs encode *relationships* — callers, callees, tests-for, imports — that grep and filename matching cannot see. For an explanation, relationships are the substrate of reasoning. Reach for grep only when the graph genuinely doesn't cover what you need.

**Default workflow when a graph MCP is present:**

1. `get_architecture_overview` — top-level community structure, gives you the shape of the codebase before you ask any narrower question.
2. `semantic_search_nodes` — find the functions/classes named by the user's question (or its synonyms). Avoid keyword-only matches; use the question's nouns and likely renames.
3. `query_graph` — pull `callers_of`, `callees_of`, `imports_of`, `tests_for` on the seed nodes. This is how you learn what the code *has to satisfy* (tests) and *depends on* (imports), which feed the constraints section of the answer.
4. `get_impact_radius` — only when the explanation is about a change or "what depends on this?".

**Fallback (no graph available):** dispatch the `Explore` subagent in parallel for the categories below. Keep searches narrow — the synthesis context must stay small.

> **Don't have a code-graph MCP yet?** Install `code-review-graph` from <https://github.com/tirth8205/code-review-graph>. Once it's wired into your MCP client, the tools above (`get_architecture_overview`, `semantic_search_nodes`, `query_graph`, `get_impact_radius`, `detect_changes`, `get_affected_flows`) become available automatically. Without it, every "how does this work" answer pays the relationship-reconstruction cost on every call.

**Focus search on:**
- Core implementation files for the topic
- Configuration files related to the topic (encode environment constraints)
- Test files that demonstrate the concept (encode behavioral constraints)
- Documentation or README sections (encode intent constraints)
- Recent changes or additions (encode the "why did this move recently" signal)

### Step 3: Analyze and Synthesize
**Read key files identified:**
- Use Read tool to examine main implementation
- Look for entry points, main classes/functions
- Identify data structures and algorithms
- Note design patterns and architectural choices

**Answer structure (first-principles ordering):**

The ordering below is deliberate. Constraints come *before* code, because the code is the consequence — not the starting point. If you find yourself wanting to lead with components, stop and write the constraint section first.

1. **The Problem** — What real-world need creates this code? State it in plain language, no jargon. If the user could solve this with nothing (a sticky note, a shell one-liner, manual work), say so and explain why that doesn't scale.
2. **The Constraints** — What inescapable facts make the problem hard? (Browser sandbox, network limits, latency, security boundary, language semantics, hardware.) List them as bullet points. Each constraint should later "explain" some piece of the design.
3. **The Derivation** — Walk from constraints to design. *"Given (1) and (2), the cheapest thing that could possibly work is X, because Y is ruled out by constraint Z."* This is the heart of the explanation. By the end of this section, the reader should be able to predict the architecture before you describe it.
4. **The Code** — *Now* point at the implementation. File paths and line numbers. Each piece of code should map to a derivation step from (3): "this satisfies constraint A", "this is the O(N) alternative to the naive O(N²) approach we ruled out".
5. **Where the design pays off / breaks down** — Honestly: what does this design make easy? What does it make hard? Which future change would force a rewrite?
6. **Related Components** — Only if relevant; what else interacts with this and why.

**Sanity check before sending:** If you deleted every code reference and file path from your answer, would the *reasoning* still hold up as an explanation? If yes, you've explained from first principles. If no, you've summarized code and dressed it up.

### Step 4: Provide Examples
**Create minimal, focused examples:**

**Visual diagrams (Excalidraw MCP):**
When the explanation would clearly benefit from a visual — architecture overviews, multi-component data flows, state machines, request/response traces with 3+ hops, or dependency relationships — call the Excalidraw MCP to render a diagram alongside the text.

Trigger an Excalidraw call when ANY of these are true:
- The question is "how does X system work?" and involves 3+ components
- You're tracing a request/data flow across services
- You're showing relationships between modules (graph-shaped, not linear)
- The user explicitly asks for a diagram, "draw", "visualize", or "show me visually"

Skip the diagram when:
- The explanation is about a single function or one file
- A code snippet alone makes the concept obvious
- The user asks a quick "what is X" lookup question

**How to call it:** Invoke the Excalidraw MCP tool (typically `mcp__excalidraw__create_drawing` or equivalent — check available tools at runtime). Pass a concise scene description with labeled boxes for components and arrows for relationships. Keep diagrams to ≤8 nodes; for larger systems, split into 2 focused diagrams (e.g., "top-level architecture" + "detailed request flow"). Reference the diagram inline in the explanation, then continue with code examples below it.

If the Excalidraw MCP isn't available in the current session, fall back to an ASCII/mermaid diagram in the response and note that Excalidraw rendering was skipped.

> **Don't have the Excalidraw MCP yet?** Setup instructions: <https://plus.excalidraw.com/docs/mcp>. Once installed, tools like `mcp__excalidraw__create_scene` and `mcp__excalidraw__edit_scene_content` become available and the skill will render diagrams to your workspace instead of falling back to ASCII.


| Topic | Example Approach |
|--------|-----------------|
| **MCP Connection** | Show `client = MCPClient("name", "python3", ["server.py"]); await client.connect()` |
| **Query Routing** | Show `router = QueryAnalyzer(); result = router.analyze("search files")` |
| **Tool Discovery** | Show `await client._discover_tools(); print(client.tools)` |
| **Multi-agent Coordination** | Show `orchestrator = CrewAIOrchestrator(); await orchestrator.run_query()` |
| **Batch Processing** | Show `processor = BatchMCPProcessor(); results = await processor.process_batch()` |

**Example format:**
```python
# Example: How query routing works
from routing.query_analyzer import QueryAnalyzer

# 1. Create analyzer
analyzer = QueryAnalyzer()

# 2. Analyze user query
result = analyzer.analyze("find Python files with async functions")

# 3. Get routing decision
if result.intent == QueryIntent.CODE_ANALYSIS:
    print("Route to code analysis MCPs")
    print(f"Confidence: {result.confidence:.2f}")
```

## Topics and Explanations

### When asked about "Query Routing"
**Core flow to explain:**
1. User query enters CLI → MasterMCPServer
2. QueryAnalyzer analyzes for intent and keywords
3. AIRouter (if available) uses LLM for complex routing
4. LearningRouter adds user feedback and patterns
5. ToolRegistry matches against available MCP tools
6. Route to best MCP(s) with suggested tool/arguments

**Key files:** `query_analyzer.py`, `ai_router.py`, `learning_router.py`, `tool_registry.py`

### When asked about "MCP Connections"
**Core flow to explain:**
1. MCPClient/HTTPMCPClient created from config
2. `connect()` spawns subprocess or creates HTTP session
3. `_initialize()` sends MCP protocol handshake
4. `_discover_tools()` calls `tools/list` method
5. Tools stored as `MCPTool` objects in client.tools list
6. `call_tool()` executes via JSON-RPC

**Key files:** `mcp_client.py`, `master_mcp_server.py`

### When asked about "Tool Discovery"
**Core flow to explain:**
1. MCP server receives `tools/list` JSON-RPC request
2. Server responds with tool definitions including schemas
3. Client parses response and creates `MCPTool` objects
4. Tools registered in `ToolRegistry` with metadata
5. ToolRegistry provides search and matching capabilities

**Key files:** `mcp_client.py:110`, `tool_registry.py`, `master_mcp_server.py:394`

### When asked about "Multi-Agent Orchestration"
**Core flow to explain:**
1. When query complexity > threshold, enable multi-agent
2. CrewAIOrchestrator creates specialist agents
3. Each agent gets subset of MCP tools relevant to their role
4. Agents execute in parallel, share context
5. Results aggregated and prioritized
6. Fallback to SimpleMultiMCPHandler if CrewAI unavailable

**Key files:** `agent_orchestrator_crewai.py`, `simple_multi_mcp.py`, `master_mcp_server.py:768`

### When asked about "Batch Processing"
**Core flow to explain:**
1. For >5 MCPs, switch to batch mode
2. BatchMCPProcessor groups calls by execution strategy
3. ToolCallInterceptor optimizes concurrent calls
4. SingleFileExecutor generates isolated execution scripts
5. DockerSandbox provides isolated execution environment
6. ResultAggregator combines and prioritizes results

**Key files:** `batch_mcp_processor.py`, `batch_executor.py`, `single_file_generator.py`

## Quality Guidelines

**ALWAYS:**
- Lead with the underlying problem and constraints, not with code or components
- Derive the design — show that given the constraints, the architecture is (close to) inevitable
- Name the simpler approach you ruled out, and which constraint killed it
- Include file paths and line numbers — but only *after* the derivation, as the "code is where this idea lives"
- Be honest when a choice is arbitrary convention rather than a principled derivation
- Use code snippets as evidence for the derivation, not as the explanation itself
- Call the Excalidraw MCP for visual diagrams when explaining multi-component systems, data flows, or architecture (see Step 4 for triggers)

**NEVER:**
- Open with "this function does X" or a component list — that's description, not explanation
- Summarize what the code does and call it an explanation
- Skip the "why couldn't a simpler approach work?" question
- Manufacture fake first principles to justify an arbitrary design choice — say it's a convention instead
- Explain line-by-line code without anchoring each line to a constraint or requirement
- Assume the reader knows all terminology
- Give vague explanations without concrete code references

## Common Question Patterns

| User Question | Response Strategy |
|---------------|------------------|
| "How does routing work?" | Show QueryAnalyzer → AIRouter → ToolRegistry flow with example |
| "What happens when I run a query?" | Trace CLI → Server → Router → MCP → Response |
| "Why use CrewAI?" | Explain multi-agent benefits and fallback mechanism |
| "How are tools discovered?" | Show JSON-RPC tools/list → MCPTool → Registry flow |
| "What's batch processing?" | Explain >5 MCPs → batch mode → Docker isolation |
| "How do I add a new MCP?" | Show config.json format → auto-detection → registration |

## Depth Control

**Optional parameter: depth=[basic|detailed|expert]**

| Depth | Content Focus |
|--------|---------------|
| `basic` | High-level overview, main concepts, simple examples |
| `detailed` | Component interactions, code examples, design reasoning |  
| `expert` | Implementation details, edge cases, performance considerations |

**Default:** `depth=basic` unless user specifies otherwise

## Example Response Structure

```markdown
## How Query Routing Works

**Core Concept:** The system uses a multi-tier routing strategy to match user queries to the best available MCP tools.

### Key Components

1. **QueryAnalyzer** (`routing/query_analyzer.py`) - Rule-based intent detection
2. **AIRouter** (`routing/ai_router.py`) - LLM-powered routing for complex queries  
3. **ToolRegistry** (`tools/tool_registry.py`) - Tool matching and discovery
4. **LearningRouter** (`routing/learning_router.py`) - User feedback and pattern learning

### How It Works

```python
# 1. User query enters system
user_query = "find async functions in Python files"

# 2. QueryAnalyzer analyzes intent
analyzer = QueryAnalyzer()
result = analyzer.analyze(user_query)
# result.intent = QueryIntent.CODE_ANALYSIS
# result.confidence = 0.85

# 3. If high confidence, use script-based routing
if result.confidence > 0.8:
    # Use ToolRegistry for direct tool matching
    registry = get_registry()
    matches = registry.find_tools_for_query(user_query)
else:
    # Use AI for complex routing
    router = AIRouter()
    suggestions = router.analyze_query_with_ai(user_query)
```

### Why This Design

- **Fallback Chain:** Script → AI → Direct tool matching
- **Performance:** Quick rule-based routing for common patterns
- **Flexibility:** AI handles complex or ambiguous queries
- **Learning:** User feedback improves routing over time

### Example Usage

```python
# Simple routing example
from routing.query_analyzer import QueryAnalyzer
from tools.tool_registry import get_registry

analyzer = QueryAnalyzer()
registry = get_registry()

# Route a query
query = "analyze this Python code"
analysis = analyzer.analyze(query)
best_tools = registry.find_tools_for_query(query)

print(f"Intent: {analysis.intent}")
print(f"Best tools: {[t.name for t in best_tools[:3]]}")
```

### Related Components

- **MCP Discovery:** `server/mcp_client.py:_discover_tools()`
- **Tool Execution:** `server/master_mcp_server.py:_execute_tool()`
- **Result Aggregation:** `batch_mcp_sandbox/result_processor.py`
```

This structure ensures comprehensive explanations with concrete examples for any codebase question.