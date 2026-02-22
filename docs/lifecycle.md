# Architecture Governance Lifecycle

> Slide-by-slide content with mermaid diagrams for the leadership presentation.
> Render in any markdown preview to screenshot diagrams for PowerPoint.

---

## Slide 1: The Problem Today

```mermaid
flowchart LR
    classDef current fill:#DC2626,color:#fff,stroke:#B91C1C
    classDef gap fill:#991B1B,color:#fff,stroke:#7F1D1D

    subgraph today [Today]
        direction TB
        A1["Architects write in<br/>Confluence (HTML)"]:::current
        A2["Diagrams as images<br/>(Draw.io, screenshots)"]:::current
        A3["No automated<br/>enforcement"]:::current
        A4["Manual review<br/>(inconsistent)"]:::current
        A1 --- A2
        A3 --- A4
    end

    subgraph gaps [The Gaps]
        direction TB
        G1["Not LLM-readable"]:::gap
        G2["Not machine-parseable"]:::gap
        G3["No audit trail<br/>for changes"]:::gap
        G4["No governance<br/>scorecard"]:::gap
        G1 --- G2
        G3 --- G4
    end

    today --> gaps
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#DC2626;border-radius:2px;vertical-align:middle"></span> Current State &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#991B1B;border-radius:2px;vertical-align:middle"></span> Resulting Gaps</sub></p>

### Talking Points

- Architecture documentation today lives in Confluence as unstructured HTML with embedded images
- No automated enforcement of patterns, standards, or security rules -- reviews are manual and inconsistent
- Confluence content is not usable by LLMs or automation tools -- it's HTML with proprietary markup, not clean text
- No standardized audit trail for architectural decisions -- Confluence page history is opaque
- No quantifiable governance scorecard -- compliance is subjective

### Speaker Notes

The core issue: we have knowledge locked in a format that neither humans can consistently govern nor machines can process. Every review is ad-hoc, and there's no way to scale enforcement as the organization grows.

---

## Slide 2: What We're Prescribing

```mermaid
flowchart LR
    classDef arch fill:#059669,color:#fff,stroke:#047857
    classDef infra fill:#0891B2,color:#fff,stroke:#0E7490
    classDef publish fill:#7C3AED,color:#fff,stroke:#6D28D9

    subgraph authoring [How Architects Author]
        direction TB
        ED["Editor of Choice<br/>(VSCode, IntelliJ, etc.)"]:::arch
        MD["Markdown<br/>(plain text)"]:::arch
        DG["Diagrams as Code<br/>(Mermaid)"]:::arch
        ED --> MD
        ED --> DG
    end

    subgraph storage [Where It Lives]
        direction TB
        GH["GitHub<br/>(system of record)"]:::infra
        GC["Git Commits<br/>(audit trail)"]:::infra
        GH --> GC
    end

    subgraph output [How It's Shared]
        direction TB
        CF["Confluence<br/>(auto-published,<br/>read-only view)"]:::publish
        DD["DevDocs / Static Site<br/>(visualization)"]:::publish
    end

    authoring -->|"commit"| storage
    storage -->|"CI/CD<br/>auto-publish"| output
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Solution Architect &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#0891B2;border-radius:2px;vertical-align:middle"></span> Infrastructure &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Publishing</sub></p>

### Talking Points

- **Format:** Architects author in Markdown + Mermaid diagrams-as-code -- plain text, version-controllable, LLM-readable
- **Tooling:** Use VSCode or any editor of choice on their machines -- no proprietary tooling lock-in
- **System of Record:** GitHub -- every change is a git commit with full traceability (who, what, when, why)
- **Sharing:** Auto-published to Confluence (read-only) and/or DevDocs for stakeholder consumption
- This is the same toolchain engineers already use -- architects join the same workflow

### Speaker Notes

We're not inventing a new tool. We're adopting the same markdown + git workflow that engineering uses, applied to architecture documentation. The format is the enabler: plain-text markdown is machine-readable, version-controllable, and universally supported.

---

## Slide 3: Two Lifecycles, One Platform

```mermaid
flowchart TB
    classDef sme fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef gov fill:#D97706,color:#fff,stroke:#B45309
    classDef arch fill:#059669,color:#fff,stroke:#047857

    subgraph smeFlow ["SME / Governance Author"]
        direction LR
        S1["Ingest from<br/>Confluence (Day 0)"]:::sme --> S2["Author Rules<br/>& Skills"]:::sme --> S3["SIG / Working Group<br/>Review & Merge"]:::sme
    end

    subgraph contribs ["Contributions"]
        direction LR
        R["Rules indexed into<br/>knowledge base"]:::sme ~~~ SK["Skills executed<br/>in pipeline"]:::sme
    end

    GA["Governance Agent"]:::gov

    subgraph archFlow ["Solution Architect"]
        direction LR
        A1["Author Architecture<br/>(Markdown + Mermaid)"]:::arch --> A2["Commit to GitHub"]:::arch
        A3["Scorecard<br/>PASS / WARN / FAIL"]:::arch
        A4["Publish"]:::arch
    end

    smeFlow --> contribs --> GA
    A2 --> GA
    GA --> A3
    A3 -->|"Pass"| A4
    A3 -.->|"Fail / Warn"| A1
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> SME / Governance Author &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Governance Agent &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Solution Architect</sub></p>

### Talking Points

- **Two personas, one platform:** SMEs build the governance, Solution Architects consume it -- both work in markdown + git
- **SME lifecycle (left):**
  - Day 0: existing Confluence content auto-ingested and converted to markdown (don't start from scratch)
  - Ongoing: author rules and skills in markdown, submit PRs under Inner Sourcing model
  - All contributions reviewed by a SIG or Working Group (Nucleus-style governance) before merge
- **Two types of SME contributions:**
  - **Rules/Standards** -- indexed into the knowledge base for agents to validate against
  - **Skills** -- executable packages that run as active validation steps in the pipeline
- **Solution Architect lifecycle (right):**
  - Author architecture in markdown + mermaid, commit to GitHub
  - Governance agent auto-triggers, validates against rules AND executes contributed skills
  - Scorecard (PASS/WARN/FAIL) -- iterate if needed, publish when passing
- **The governance agent is the bridge** connecting both lifecycles

### Speaker Notes

This is the centerpiece slide. The left side shows how governance content is built and contributed (with proper organizational oversight). The right side shows how architects experience it. The governance agent in the center is the automated bridge -- it consumes everything SMEs produce and applies it to everything architects create. No manual review bottleneck.

---

## Slide 4: How Governance Works

```mermaid
flowchart TB
    classDef arch fill:#059669,color:#fff,stroke:#047857
    classDef infra fill:#0891B2,color:#fff,stroke:#0E7490
    classDef gov fill:#D97706,color:#fff,stroke:#B45309
    classDef agent fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef skill fill:#7C3AED,color:#fff,stroke:#6D28D9

    subgraph trigger ["Step 1: Trigger & Ingest"]
        direction LR
        A1["Solution Architect<br/>commits to GitHub"]:::arch --> GH["GitHub triggers<br/>governance pipeline"]:::infra --> GA["Governance Agent<br/>(orchestrator)"]:::gov --> IA["Ingestion Agent<br/>parses & validates"]:::gov
    end

    subgraph parallel ["Step 2: Parallel Validation"]
        direction LR
        PA["Patterns Agent<br/>(30% weight)"]:::agent ~~~ SA["Standards Agent<br/>(30% weight)"]:::agent ~~~ SEA["Security Agent<br/>(40% weight)"]:::agent ~~~ SK["Contributed Skills<br/>(auto-discovered)"]:::skill
    end

    subgraph consolidate ["Step 3: Consolidate"]
        direction LR
        MR["Merge Reports<br/>(weighted scoring)"]:::gov --> SC["Governance Scorecard<br/>PASS / WARN / FAIL"]:::gov --> A2["Solution Architect"]:::arch
    end

    trigger --> parallel --> consolidate
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Architect &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#0891B2;border-radius:2px;vertical-align:middle"></span> Infrastructure &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Pipeline &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> Validation Agents &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Contributed Skills</sub></p>

### Talking Points

- **Trigger:** Governance agent executes automatically on commit to GitHub -- no manual invocation needed
- **Ingestion:** Content is parsed and validated for structure
- **Parallel validation:** Three built-in agents run simultaneously, plus any contributed skills
  - Patterns Agent (30% weight) -- design patterns, anti-patterns
  - Standards Agent (30% weight) -- naming conventions, documentation standards
  - Security Agent (40% weight) -- security controls, vulnerabilities
  - Contributed Skills -- discovered and executed alongside built-in agents
- **Scoring:** Weighted average produces a single governance score
  - PASS: score >= 70
  - WARN: score 50-69
  - FAIL: score < 50
- **Output:** Merged report + HTML dashboard delivered back to the architect

### Speaker Notes

The key message: this is fully automated. The architect commits, the pipeline runs, and they get a scorecard. The weighting reflects organizational priorities -- security is weighted highest at 40%. Contributed skills from other teams are auto-discovered and run as first-class participants in the pipeline.

---

## Slide 5: System of Record and Sync Strategy

```mermaid
flowchart LR
    classDef arch fill:#059669,color:#fff,stroke:#047857
    classDef infra fill:#0891B2,color:#fff,stroke:#0E7490
    classDef gov fill:#D97706,color:#fff,stroke:#B45309
    classDef publish fill:#7C3AED,color:#fff,stroke:#6D28D9
    classDef viewer fill:#6B7280,color:#fff,stroke:#4B5563

    subgraph author [Architect Authors]
        ED["Editor of Choice"]:::arch
        MD["Markdown + Mermaid"]:::arch
        ED --> MD
    end

    subgraph sor [Source of Truth]
        direction TB
        GH["GitHub Repository"]:::infra
        GC["Git Commits<br/>= Audit Trail"]:::infra
        GOV["Governance Agent<br/>validates on commit"]:::gov
        GH --> GC
        GH --> GOV
        GC ~~~ GOV
    end

    subgraph out [Auto-Published Views]
        direction TB
        CF["Confluence<br/>(read-only mirror)"]:::publish
        DD["DevDocs / Static Site<br/>(visualization)"]:::publish
        CF ~~~ DD
    end

    author -->|"commit"| sor
    sor -->|"CI/CD on merge<br/>(one-way sync)"| out
    out -->|"stakeholders<br/>view here"| SH["Stakeholders"]:::viewer
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Architect &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#0891B2;border-radius:2px;vertical-align:middle"></span> Infrastructure &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Governance &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Publishing &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#6B7280;border-radius:2px;vertical-align:middle"></span> Stakeholders</sub></p>

### Talking Points

- **GitHub is the single source of truth** -- all architecture artifacts live as markdown + mermaid in git repos
- **Change history = git commits** -- who changed what, when, and why -- full audit trail with no ambiguity
- **Auto-publish to Confluence on merge** -- CI/CD pipeline pushes rendered markdown to Confluence via API after each merge to main
- **Confluence becomes a read-only view** -- stakeholders who prefer Confluence still see the content, but it's always in sync
- **One-way sync eliminates drift** -- there is no manual copy/paste, no "which version is correct?" problem
- Architects never touch Confluence directly -- they author in their editor, commit, and the pipeline handles the rest

### Speaker Notes

This is critical for leadership: we're not asking anyone to give up Confluence as a viewing experience. Stakeholders still see content in Confluence if they prefer. But the source of truth is git, and the sync is automated and one-way. This eliminates the "two sources of truth" problem that plagues organizations using both tools.

---

## Slide 6: Confluence Migration Path

```mermaid
flowchart TB
    classDef newTrack fill:#059669,color:#fff,stroke:#047857
    classDef migrateTrack fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef gov fill:#D97706,color:#fff,stroke:#B45309
    classDef publish fill:#7C3AED,color:#fff,stroke:#6D28D9

    subgraph trackA [Track A: New Content]
        direction LR
        NA1["Author natively<br/>in Markdown + Mermaid"]:::newTrack
        NA2["Commit to<br/>GitHub"]:::newTrack
        NA3["Governance<br/>validates"]:::gov
        NA4["Auto-publish to<br/>Confluence"]:::publish
        NA1 --> NA2 --> NA3 --> NA4
    end

    subgraph trackB [Track B: Existing Confluence Content]
        direction LR
        NB1["Ingestion tool<br/>downloads page"]:::migrateTrack
        NB2["Auto-convert<br/>HTML to Markdown"]:::migrateTrack
        NB3["Diagrams converted<br/>Draw.io/PlantUML<br/>to Mermaid"]:::migrateTrack
        NB4["SME reviews<br/>converted baseline"]:::migrateTrack
        NB5["Commit to<br/>GitHub"]:::migrateTrack
        NB6["Governance<br/>validates"]:::gov
        NB7["Auto-publish<br/>back to Confluence"]:::publish
        NB1 --> NB2 --> NB3 --> NB4 --> NB5 --> NB6 --> NB7
    end

    trackB -->|"after initial<br/>migration"| trackA
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> New Content &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> Migration &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Governance &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Publishing</sub></p>

### Talking Points

- **Track A (new content):** Authored natively in markdown + mermaid from day one -- straight into the governed pipeline
- **Track B (existing content):** Ingestion tool auto-converts Confluence pages to clean markdown
  - HTML to markdown conversion
  - Draw.io diagrams converted to Mermaid (XML parsing, no LLM cost)
  - PlantUML converted to Mermaid (parser-based, zero cost)
  - Images converted to Mermaid (vision-based, where needed)
- **SME review:** Converted content is reviewed for accuracy before committing as the baseline
- **Convergence:** After initial migration, Track B content joins Track A -- everything is markdown-native going forward
- **Already built:** The ingestion and conversion tooling is fully operational today

### Speaker Notes

This is how we address the "we already have years of content in Confluence" concern. We don't ask anyone to re-author from scratch. The ingestion tool handles the conversion, SMEs review it, and from that point forward it's all markdown-native. The conversion tooling for Draw.io and PlantUML is parser-based (not LLM), so it's fast and free.

---

## Slide 7: Business Benefits

```mermaid
flowchart LR
    classDef enforce fill:#DC2626,color:#fff,stroke:#B91C1C
    classDef llm fill:#D97706,color:#fff,stroke:#B45309
    classDef scalable fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef trace fill:#059669,color:#fff,stroke:#047857
    classDef vizz fill:#7C3AED,color:#fff,stroke:#6D28D9

    subgraph enforcement [Enforcement]
        direction TB
        E1["Automated validation<br/>of patterns, standards,<br/>security"]:::enforce
        E2["Consistent scoring<br/>across all architectures"]:::enforce
        E3["No manual review<br/>bottleneck"]:::enforce
        E1 ~~~ E2 ~~~ E3
    end

    subgraph llmReady [LLM-Ready]
        direction TB
        L1["Markdown is<br/>machine-readable"]:::llm
        L2["Enables AI-assisted<br/>architecture review"]:::llm
        L3["Confluence HTML<br/>is not LLM-friendly"]:::llm
        L1 ~~~ L2 ~~~ L3
    end

    subgraph scale [Scalable Governance]
        direction TB
        SC1["Teams contribute<br/>rules as skills"]:::scalable
        SC2["Inner Sourcing +<br/>SIG/Working Group model"]:::scalable
        SC3["Zero coordination<br/>after initial setup"]:::scalable
        SC1 ~~~ SC2 ~~~ SC3
    end

    subgraph traceBlock [Traceability]
        direction TB
        T1["Git commits =<br/>full audit trail"]:::trace
        T2["Every decision<br/>is versioned"]:::trace
        T3["Compliance is<br/>quantifiable"]:::trace
        T1 ~~~ T2 ~~~ T3
    end

    subgraph viz ["Stakeholder&nbsp;Communication"]
        direction TB
        V1["Auto-publish to<br/>Confluence / DevDocs"]:::vizz
        V2["Mermaid diagrams<br/>render natively"]:::vizz
        V3["Architecture visible<br/>to all stakeholders"]:::vizz
        V1 ~~~ V2 ~~~ V3
    end

    enforcement ~~~ llmReady ~~~ scale ~~~ traceBlock ~~~ viz
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#DC2626;border-radius:2px;vertical-align:middle"></span> Enforcement &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> LLM-Ready &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> Scalable &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Traceability &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Communication</sub></p>

### Talking Points

- **Enforcement of best practices:** Automated, consistent validation of every architecture against organizational patterns, standards, and security rules -- no subjectivity
- **LLM-ready documentation:** Markdown is machine-readable; Confluence HTML is not. This positions architecture docs for AI-assisted review and generation
- **Scalable governance:** Teams contribute their own rules via Inner Sourcing model under SIG/Working Group oversight. After initial setup, zero coordination overhead
- **Full traceability:** Git commits provide complete audit trail -- who changed what, when, why. Compliance becomes quantifiable via governance scores
- **Stakeholder communication:** Architecture is auto-published and visualized for stakeholders via Confluence or DevDocs -- no extra effort from architects

### Speaker Notes

Tie every benefit to an organizational outcome. Enforcement reduces risk. LLM-readiness future-proofs the investment. Scalability means this doesn't become a bottleneck as the org grows. Traceability satisfies audit requirements. And auto-publishing means architects focus on architecture, not formatting Confluence pages.

---

## Slide 8: Cross-Team Ecosystem -- Already in Motion

```mermaid
flowchart TB
    classDef team fill:#7C3AED,color:#fff,stroke:#6D28D9
    classDef govrepo fill:#D97706,color:#fff,stroke:#B45309
    classDef consumer fill:#059669,color:#fff,stroke:#047857
    classDef sig fill:#2563EB,color:#fff,stroke:#1D4ED8

    subgraph teams [Contributing Teams]
        direction LR
        subgraph teamA [Team A]
            direction TB
            TA_REPO["Git Repo"]:::team
            TA_SKILL["Skill: Markdown<br/>instruction files"]:::team
            TA_REPO --> TA_SKILL
        end
        subgraph teamB [Team B]
            direction TB
            TB_REPO["Git Repo"]:::team
            TB_SKILL["Skill: Markdown<br/>guidelines +<br/>Python scripts"]:::team
            TB_REPO --> TB_SKILL
        end
        subgraph teamN [Team N ...]
            direction TB
            TN_REPO["Git Repo"]:::team
            TN_SKILL["Skill: Any markdown<br/>+ optional tooling"]:::team
            TN_REPO --> TN_SKILL
        end
        teamA ~~~ teamB ~~~ teamN
    end

    subgraph sigReview ["SIG&nbsp;/&nbsp;Working&nbsp;Group&nbsp;—&nbsp;Inner&nbsp;Source&nbsp;Model"]
        direction LR
        SIG_PR["PRs reviewed by<br/>cross-team SIG"]:::sig
        SIG_STD["Contribution standards<br/>enforced"]:::sig
        SIG_APP["Approved skills<br/>merged & versioned"]:::sig
        SIG_PR --> SIG_STD --> SIG_APP
    end

    subgraph govRepo [Architecture Governance Repo]
        direction LR
        SUB["Git Submodules<br/>(pull in external skills)"]:::govrepo
        DISC["Auto-Discovery<br/>(skills registered<br/>by category tag)"]:::govrepo
        SUB --> DISC
    end

    subgraph consumers [Architecture Governance]
        direction LR
        EX["Extract Rules<br/>from contributed skills"]:::consumer
        AG["Apply to Architecture<br/>Governance Pipeline"]:::consumer
        EX --> AG
    end

    teams -->|"PR"| sigReview -->|"approved"| govRepo --> consumers
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> External Teams &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Governance Repo &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Consumers &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> SIG / Working Group</sub></p>

### Talking Points

- **Already in production:** Other engineering teams have built governance skills (markdown instructions, Python scripts) for their own code governance purposes
- **Team A:** Created a skill as a set of markdown instruction files in their own git repo -- integrated via git submodules
- **Team B:** Created a skill with markdown guidelines + Python scripts for code governance -- also integrated via submodules
- **We extract the rules:** Their skills contain rich patterns, guidelines, and standards -- we pull those rules out and apply them to architecture governance
- **Same governance model:** All contributions follow Inner Sourcing principles under SIG/Working Group review
- **Key message:** This is not a greenfield experiment -- teams are already producing governance content in markdown + git, and we extract and reuse their rules for architecture validation

### Speaker Notes

This is powerful proof of adoption. Two teams independently built skills for code governance, and we extract the rules embedded in those skills -- patterns, standards, guidelines -- and apply them to architecture governance. The submodule model means each team owns their skill in their own repo, pushes updates on their own schedule, and the governance pipeline picks up rule changes automatically. We don't do code governance ourselves -- we leverage the rules others have codified.

---

## Slide 9: What's Already Built

```mermaid
flowchart LR
    classDef agentColor fill:#D97706,color:#fff,stroke:#B45309
    classDef convertColor fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef reportColor fill:#059669,color:#fff,stroke:#047857
    classDef ecoColor fill:#7C3AED,color:#fff,stroke:#6D28D9
    classDef kbColor fill:#0891B2,color:#fff,stroke:#0E7490

    subgraph agents [5 AI Agents]
        direction TB
        GOV["Governance Agent<br/>(orchestrator)"]:::agentColor
        ING["Ingestion Agent<br/>(Confluence to Markdown)"]:::agentColor
        PAT["Patterns Agent"]:::agentColor
        STD["Standards Agent"]:::agentColor
        SEC["Security Agent"]:::agentColor
    end

    subgraph converters [Diagram Converters]
        direction TB
        DIO["Draw.io to Mermaid<br/>(XML parser, zero cost)"]:::convertColor
        PML["PlantUML to Mermaid<br/>(parser, zero cost)"]:::convertColor
        IMG["Image to Mermaid<br/>(vision-based)"]:::convertColor
    end

    subgraph reporting [Reporting]
        direction TB
        MRG["Weighted Score Merge<br/>(30/30/40)"]:::reportColor
        HTML["HTML Dashboard<br/>Generation"]:::reportColor
    end

    subgraph ecosystem [Ecosystem]
        direction TB
        SUBS["Git Submodule<br/>Integration"]:::ecoColor
        AUTO["Auto-Discovery<br/>by Category"]:::ecoColor
        XTEAM["Cross-Team Skills<br/>Already Integrated"]:::ecoColor
    end

    subgraph kb [Knowledge Base]
        direction TB
        IDX["Indexed Rules<br/>(patterns, standards,<br/>security)"]:::kbColor
        EXT["Rules Extraction<br/>+ Staleness Check"]:::kbColor
    end
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> AI Agents &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> Converters &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Reporting &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#7C3AED;border-radius:2px;vertical-align:middle"></span> Ecosystem &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#0891B2;border-radius:2px;vertical-align:middle"></span> Knowledge Base</sub></p>

### Talking Points

- **5 AI agents** operational: governance orchestrator, ingestion, patterns, standards, security
- **Diagram conversion** built and working:
  - Draw.io XML to Mermaid (parser-based, zero LLM cost)
  - PlantUML to Mermaid (parser-based, zero cost)
  - Image to Mermaid (vision-based, for non-parseable diagrams)
- **Weighted scoring** with merged reports: Patterns 30%, Standards 30%, Security 40%
- **HTML dashboard** generation for governance results
- **Multi-team skill contribution** model via git submodules with auto-discovery by category tag
- **Cross-team skills** from two engineering teams already integrated and running
- **Knowledge base** with indexed rules, automated extraction, and staleness checking

### Speaker Notes

Everything described in the previous slides is not aspirational -- the core platform is built and operational. The agents run, the converters work, the scoring produces results, and cross-team skills are already integrated. What remains is the CI/CD trigger on commit (requires engineering partnership) and the auto-publish to Confluence pipeline.

---

## Slide 10: Rollout Plan

```mermaid
flowchart LR
    classDef p1 fill:#0891B2,color:#fff,stroke:#0E7490
    classDef p2 fill:#2563EB,color:#fff,stroke:#1D4ED8
    classDef p3 fill:#D97706,color:#fff,stroke:#B45309
    classDef p4 fill:#059669,color:#fff,stroke:#047857

    subgraph phase1 [Phase 1: Pilot]
        direction TB
        P1A["Select one<br/>architecture team"]:::p1
        P1B["GitHub-native<br/>workflow"]:::p1
        P1C["Run governance<br/>manually via IDE"]:::p1
        P1A --> P1B --> P1C
    end

    subgraph phase2 [Phase 2: Migrate]
        direction TB
        P2A["Convert high-value<br/>Confluence pages"]:::p2
        P2B["SME review<br/>converted baselines"]:::p2
        P2C["Establish governance<br/>knowledge base"]:::p2
        P2A --> P2B --> P2C
    end

    subgraph phase3 [Phase 3: Automate]
        direction TB
        P3A["Enable governance-on-commit<br/>via GitHub Actions"]:::p3
        P3B["Auto-publish pipeline<br/>to Confluence"]:::p3
        P3C["Governance scorecards<br/>on every PR"]:::p3
        P3A --> P3B --> P3C
    end

    subgraph phase4 [Phase 4: Scale]
        direction TB
        P4A["Onboard additional<br/>architecture teams"]:::p4
        P4B["SIG/Working Groups<br/>contribute rules & skills"]:::p4
        P4C["DevDocs visualization<br/>for stakeholders"]:::p4
        P4A --> P4B --> P4C
    end

    phase1 --> phase2 --> phase3 --> phase4
```

<p align="right"><sub><span style="display:inline-block;width:10px;height:10px;background:#0891B2;border-radius:2px;vertical-align:middle"></span> Phase 1: Pilot &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#2563EB;border-radius:2px;vertical-align:middle"></span> Phase 2: Migrate &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#D97706;border-radius:2px;vertical-align:middle"></span> Phase 3: Automate &nbsp;&nbsp; <span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;vertical-align:middle"></span> Phase 4: Scale</sub></p>

### Talking Points

- **Phase 1 -- Pilot:** Select one architecture team, adopt GitHub-native markdown workflow, run governance via IDE agents (already works today)
- **Phase 2 -- Migrate:** Convert high-value existing Confluence pages using the ingestion tool, SMEs review converted baselines, build out the governance knowledge base
- **Phase 3 -- Automate:** Partner with engineering to enable governance-on-commit via GitHub Actions, set up auto-publish pipeline to Confluence, governance scorecards appear on every PR
- **Phase 4 -- Scale:** Onboard additional architecture teams, SIGs and Working Groups contribute domain-specific rules and skills, enable DevDocs or static site visualization for broader stakeholder communication

### Speaker Notes

Phase 1 is achievable immediately with what's already built. Phase 2 uses the existing ingestion tooling. Phase 3 requires engineering partnership for CI/CD integration. Phase 4 is the organizational scaling play. Each phase builds on the previous one with clear, measurable outcomes.
