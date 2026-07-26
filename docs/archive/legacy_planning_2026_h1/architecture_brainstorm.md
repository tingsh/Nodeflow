> **Historical reference — do not use as current implementation guidance.** See the [documentation authority index](../../README.md).

# Architecture Brainstorm: SaaS Pegasus + ThingsBoard vs Build Custom

> **Date:** April 2026  
> **Context:** We have SaaS Pegasus (Django/Python/HTMX/Tailwind/Postgres/Celery/Stripe) in `d:\Novena`. We're evaluating whether to integrate ThingsBoard (Java/Spring Boot/Angular/Kafka/Cassandra) or build IoT features natively in Django.

---

## 1. What We Already Have (SaaS Pegasus)

Your Pegasus instance (`novena_hub` project) already gives us:

| Feature | Status | Value |
|---------|--------|-------|
| **User Authentication** (signup, login, 2FA, Google OAuth) | ✅ Ready | Saves 2-3 weeks |
| **Teams / Multi-tenancy** | ✅ Ready | Saves 2-3 weeks |
| **Stripe Subscriptions & Billing** | ✅ Ready | Saves 3-4 weeks |
| **Role-based Access Control** | ✅ Ready | Saves 1-2 weeks |
| **API with Auth (DRF + API Keys)** | ✅ Ready | Saves 1-2 weeks |
| **Celery Background Tasks** | ✅ Ready | Saves 1 week |
| **AI/LLM Chat Interface** | ✅ Ready | Saves 1-2 weeks |
| **Docker Setup** | ✅ Ready | Saves 1 week |
| **Admin Panel (Django Admin)** | ✅ Ready | Free with Django |
| **Dark Mode / Tailwind UI** | ✅ Ready | Saves 1 week |
| **Email / Notifications** | ✅ Ready | Saves 1 week |
| **Wagtail CMS (marketing pages)** | ✅ Ready | Saves 1-2 weeks |
| **Health Checks, Sentry, CI/CD** | ✅ Ready | Saves 1 week |

**Total estimated savings: 16-24 weeks of development.** This is massive. Throwing this away to build on ThingsBoard alone would be a significant mistake at our stage.

---

## 2. What ThingsBoard Provides

ThingsBoard Community Edition (Apache 2.0, free) offers:

| Feature | CE Available? | Our Need |
|---------|--------------|----------|
| Device management (register, credentials) | ✅ | CRITICAL |
| MQTT/HTTP/CoAP transport | ✅ | CRITICAL |
| Telemetry data ingestion & storage | ✅ | CRITICAL |
| Rule engine (data processing, alerts) | ✅ | HIGH |
| Dashboards & widgets | ✅ | MEDIUM (we want our own UX) |
| Alarming system | ✅ | HIGH |
| Multi-tenancy | ✅ | HAVE (Pegasus) |
| Authentication/Users | ✅ | HAVE (Pegasus) |
| Billing/Subscriptions | ❌ | HAVE (Pegasus) |
| White-labeling | ❌ (PE only) | NEED |
| LoRaWAN/Sigfox integrations | ❌ (PE only) | FUTURE |
| Advanced RBAC | ❌ (PE only) | HAVE (Pegasus) |
| Reporting | ❌ (PE only) | FUTURE |

---

## 3. The Three Options

### Option A: SaaS Pegasus + Build IoT Layer in Django (Custom Build)
### Option B: SaaS Pegasus + ThingsBoard as Backend Service (Integration)
### Option C: ThingsBoard Only, Build Business Features on Top

Let me analyze each honestly:

---

## Option A: Build IoT Layer in Django 🔧

```
┌─────────────────────────────────────────────┐
│              YOUR DJANGO APP                │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  Auth    │ │ Billing  │ │ Teams/RBAC   │ │ ← Pegasus
│  └─────────┘ └──────────┘ └──────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Devices  │ │Dashboard │ │ Alerts/Rules │ │ ← Custom IoT Apps
│  └─────────┘ └──────────┘ └──────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  MQTT   │ │TimeSeries│ │  AI Engine   │ │ ← Custom IoT Infra
│  │ Broker  │ │  Storage │ │              │ │
│  └─────────┘ └──────────┘ └──────────────┘ │
└─────────────────────────────────────────────┘
```

**What we'd build:**
- Django models for Devices, Sensors, Telemetry
- MQTT broker integration (Mosquitto/EMQX + Django consumer)
- Time-series data storage (TimescaleDB extension on Postgres)
- Dashboard UI with real-time charts (HTMX + Chart.js/Plotly)
- Alert engine (Celery periodic tasks checking thresholds)
- Device provisioning API

**Pros:**
- ✅ Single tech stack (Python/Django) — you're fast here
- ✅ Full control over UX — plug-and-play vision is 100% ours
- ✅ No integration complexity — one codebase, one deployment
- ✅ All business logic in one place (billing ↔ device limits ↔ alerts)
- ✅ Simpler infrastructure (Postgres + TimescaleDB + Redis + Mosquitto)
- ✅ Easier to hire for (Python devs are abundant)

**Cons:**
- ❌ Must build MQTT handling, device auth, telemetry pipeline from scratch
- ❌ Must build dashboard widgets (charts, gauges, maps)
- ❌ No battle-tested rule engine — our Celery-based alerting is simpler
- ❌ Won't scale to 100K+ devices without significant re-architecture
- ❌ Time-series at scale is hard (but TimescaleDB handles SME volumes fine)

**Estimated additional build time for MVP:** 6-8 weeks

---

## Option B: SaaS Pegasus (Business Layer) + ThingsBoard (IoT Engine) 🔗

```
┌──────────────────────────┐    ┌──────────────────────────┐
│     DJANGO (Pegasus)     │    │      THINGSBOARD CE      │
│  ┌─────────┐ ┌────────┐ │    │  ┌──────┐ ┌───────────┐ │
│  │  Auth   │ │Billing │ │    │  │ MQTT │ │ Telemetry │ │
│  └─────────┘ └────────┘ │    │  └──────┘ └───────────┘ │
│  ┌─────────┐ ┌────────┐ │    │  ┌──────┐ ┌───────────┐ │
│  │ Teams   │ │  UX    │ │◄──►│  │Rules │ │ Devices   │ │
│  └─────────┘ └────────┘ │API │  └──────┘ └───────────┘ │
│  ┌─────────┐ ┌────────┐ │    │  ┌──────┐ ┌───────────┐ │
│  │  AI     │ │Onboard │ │    │  │Alerts│ │ Dashboard │ │
│  └─────────┘ └────────┘ │    │  └──────┘ └───────────┘ │
└──────────────────────────┘    └──────────────────────────┘
```

**How it works:**
- Django handles: auth, billing, teams, onboarding UX, AI features, user-facing UI
- ThingsBoard handles: device connectivity, MQTT, telemetry storage, rule engine, alerting
- They talk via ThingsBoard REST API + `tb-rest-client` Python library
- Django proxies all device/telemetry requests through its own API

**Pros:**
- ✅ ThingsBoard handles the hard IoT stuff (protocol handling, device state, rule engine)
- ✅ We keep our Pegasus UX and business logic layer
- ✅ Faster to get device connectivity working (plug in, not build)

**Cons:**
- ❌ **Two completely different tech stacks** (Java + Python running in parallel)
- ❌ **Double the infrastructure** — TB needs its own Java runtime, Kafka, Zookeeper, Cassandra/Postgres, Redis
- ❌ **Two auth systems** to keep in sync — user signs up in Django, needs a TB tenant/customer created via API
- ❌ **Debugging across two systems** is painful — "where did the data go wrong, Django or TB?"
- ❌ **Latency** — every device data request goes Django → TB API → TB DB → response → Django → user
- ❌ **Infrastructure cost** — ThingsBoard monolith needs 4-8GB RAM minimum. That's $40-80/mo just for TB
- ❌ **Tight coupling to TB internals** — if TB changes their API or data model, our integration breaks
- ❌ **Can't customize TB behavior easily** — rule engine is powerful but opaque; custom logic means Java
- ❌ **UX mismatch** — embedding TB dashboards in our UI looks like Frankenstein

**Estimated additional build time for MVP:** 4-6 weeks (faster start, but ongoing integration tax)

---

## Option C: ThingsBoard Only ☕

```
┌─────────────────────────────────────────────┐
│              THINGSBOARD PE                 │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  Auth   │ │ Devices  │ │  Dashboards  │ │
│  └─────────┘ └──────────┘ └──────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Rules   │ │Telemetry │ │   Alerts     │ │
│  └─────────┘ └──────────┘ └──────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Custom  │ │ Custom   │ │  Custom      │ │
│  │ Billing │ │ Onboard  │ │  AI Layer    │ │ ← All custom Java
│  └─────────┘ └──────────┘ └──────────────┘ │
└─────────────────────────────────────────────┘
```

**Pros:**
- ✅ Full IoT feature set out of the box
- ✅ Single platform for IoT concerns

**Cons:**
- ❌ **Lose ALL Pegasus value** (16-24 weeks of savings gone)
- ❌ **Must build billing, teams, onboarding in Java** — you're not fast in Java
- ❌ **ThingsBoard's UX is engineer-focused** — exact opposite of our "plug and play" vision
- ❌ **PE license required for white-labeling** ($$$)
- ❌ **You'd be building a worse version of ThingsBoard PE** basically for free
- ❌ **Angular frontend** — you'd need to learn Angular or rebuild the UI

**Estimated additional build time for MVP:** 10-16 weeks (essentially starting over)

---

## 4. My CTO Recommendation: Option A (Build IoT Layer in Django) ✅

> [!IMPORTANT]
> **I strongly recommend Option A — and here's the honest reasoning as your co-founder.**

### Why NOT Option B (the "integration" approach)?

I know it's tempting to think "ThingsBoard already has MQTT and device management, let's just use it." But here's what actually happens in practice:

1. **Integration tax is real and ongoing.** Every feature you build touches two systems. "Add a new device type" = Django model + TB API call + sync logic + error handling. "Show telemetry" = Django view → TB API → parse response → render. This doubles your development time on *every feature* going forward.

2. **Two infrastructure stacks = 2x ops burden.** ThingsBoard monolith needs 4-8GB RAM, Java runtime, and either Cassandra or its own Postgres instance. For a 2-person startup, maintaining a Java service you didn't write is a distraction you can't afford.

3. **Auth sync is a nightmare.** User signs up in Django → you need to create a TB customer via API → manage two sets of tokens → handle edge cases where one system succeeds and the other fails. This seems small until it causes your first data integrity bug at 3 AM.

4. **The "hard IoT stuff" isn't that hard for our scale.** We're targeting SMEs with 10-200 devices. We don't need Kafka, Zookeeper, and a distributed actor system. We need an MQTT broker (Mosquitto = 50MB RAM), a Celery consumer, and TimescaleDB for time-series data. That's it.

### Why Option A works for us right now:

| Concern | Reality at SME Scale |
|---------|---------------------|
| "MQTT is hard" | Mosquitto + Django MQTT consumer = ~200 lines of code |
| "Time-series storage is hard" | TimescaleDB on Postgres = 1 migration + hypertable creation |
| "Dashboard widgets are hard" | Chart.js/Plotly + HTMX = a few hundred lines per widget |
| "Rule engine is hard" | Celery periodic tasks + simple threshold checks = sufficient for MVP |
| "Won't scale" | TimescaleDB handles billions of rows. Mosquitto handles 100K concurrent connections. We need 1,000. |
| "Device auth is hard" | Pre-shared key + device ID. Generate at registration time. Done. |

### The Pragmatic Build Plan:

For our MVP (cold chain monitoring for SMEs), we need exactly these IoT features:

```
MVP Feature Set (Option A — Django-native):
├── Device Management
│   ├── Register device (name, type, location)         → Django Model + DRF API
│   ├── Device credentials (API key generation)        → Django Model
│   └── Device status (online/offline heartbeat)       → Celery task
│
├── Data Ingestion
│   ├── MQTT broker                                     → Mosquitto (Docker container)
│   ├── MQTT → Django consumer                          → django-mqtt or paho-mqtt + Celery
│   └── Store telemetry in TimescaleDB                  → Django Model + TimescaleDB hypertable
│
├── Dashboards
│   ├── Real-time temperature chart                     → Chart.js + HTMX polling/WebSocket
│   ├── Device list with status                         → Django template + Tailwind
│   └── Location overview map                           → Leaflet.js
│
├── Alerts
│   ├── Threshold-based alerts (temp > X)               → Celery periodic task
│   ├── Alert notifications (email, SMS, webhook)       → Celery + Django email/Twilio
│   └── Alert history log                               → Django Model
│
├── AI Layer
│   ├── Anomaly detection on telemetry                  → Python (scikit-learn/Prophet)
│   ├── Natural language insights ("Your chiller...")    → LLM API (already in Pegasus!)
│   └── Predictive maintenance suggestions              → Phase 2
│
└── Already Done (Pegasus)
    ├── User auth, 2FA, social login                    → ✅
    ├── Team management                                  → ✅
    ├── Stripe billing (per-device tiers)               → ✅
    ├── API authentication                               → ✅
    ├── Background tasks                                 → ✅
    └── Admin panel                                      → ✅
```

### Infrastructure (Simple & Cheap):

```
Production Stack (Month 1-12):
┌─────────────────────────────────────────────┐
│  Single VPS or Small Cloud Instance         │
│  (DigitalOcean $48/mo or AWS t3.medium)     │
│                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐ │
│  │  Django   │  │ Mosquitto │  │  Redis   │ │
│  │  + Celery │  │  (MQTT)   │  │  Cache   │ │
│  └──────────┘  └───────────┘  └──────────┘ │
│  ┌──────────────────────────────────────┐   │
│  │  PostgreSQL + TimescaleDB Extension  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘

Total infra cost: ~$50-100/mo for first 500 devices
```

Compare to Option B infrastructure:

```
Option B Stack:
┌──────────────────────┐  ┌──────────────────────┐
│  Django Server       │  │  ThingsBoard Server   │
│  $24/mo              │  │  $48/mo (4GB RAM min) │
│  + Celery            │  │  + Kafka              │
│  + Redis             │  │  + Zookeeper          │
│                      │  │  + Cassandra/Postgres  │
│  PostgreSQL          │  │  + Redis              │
│  $15/mo              │  │  $15/mo               │
└──────────────────────┘  └──────────────────────┘

Total infra cost: ~$100-150/mo minimum, even with 0 devices
```

---

## 5. When Would I Change My Mind?

I'd reconsider Option B (ThingsBoard integration) ONLY if:

1. **We needed 10,000+ concurrent device connections** on Day 1 (we won't)
2. **We needed native OPC-UA/BACnet protocol support** at the server level (we can add edge gateways later)
3. **We raised funding** and had a 5+ person engineering team that could maintain two stacks
4. **An enterprise customer required** ThingsBoard compatibility specifically

> [!NOTE]
> **The beautiful thing about Option A is that it doesn't close any doors.** If we outgrow our Django IoT layer at 10K devices, we can migrate the IoT backend to ThingsBoard or a dedicated service at that point. But we'll have revenue, customers, and a proven product to fund that migration. Building for 100K-device scale on Day 1 with 2 founders is the classic startup trap of over-engineering.

---

## 6. Decision Summary

| Criteria | Option A (Django Custom) | Option B (Pegasus + TB) | Option C (TB Only) |
|----------|:---:|:---:|:---:|
| **Time to MVP** | 6-8 weeks | 4-6 weeks (then ongoing tax) | 10-16 weeks |
| **Tech stack complexity** | ⭐ Low (1 stack) | ⚠️ High (2 stacks) | ⚠️ Medium (unfamiliar stack) |
| **Infra cost** | ~$50-100/mo | ~$100-150/mo | ~$48-80/mo |
| **Your productivity** | 🟢 High (Python/Django) | 🟡 Medium (cross-system) | 🔴 Low (Java/Angular) |
| **UX control** | 🟢 Full | 🟡 Partial | 🔴 Limited |
| **Plug-and-play vision** | 🟢 100% our design | 🟡 Compromised | 🔴 TB's UX = not SME-friendly |
| **Scalability ceiling** | ~10K devices (then re-arch) | ~100K+ (TB handles) | ~100K+ |
| **Ongoing dev velocity** | 🟢 Fast (single codebase) | 🔴 Slow (integration tax) | 🟡 Medium |
| **Pegasus value retained** | ✅ 100% | ✅ ~80% | ❌ 0% |
| **IoT protocol depth** | Basic (MQTT/HTTP) | Deep (MQTT/CoAP/LwM2M) | Deep |

---

## 7. What We Should Build First (MVP Scope)

Based on the business analysis (cold chain = beachhead), here's the bare minimum MVP:

### Must Have (Week 1-6)
- [ ] Device registration (name, type, token generation)
- [ ] MQTT data ingestion (Mosquitto + Django consumer)
- [ ] TimescaleDB telemetry storage
- [ ] Real-time dashboard (temperature + humidity chart)
- [ ] Threshold alerts (email notification)
- [ ] Device online/offline status
- [ ] Subscription tiers with device limits (Stripe integration)

### Should Have (Week 7-10)
- [ ] Multi-site view (devices grouped by location)
- [ ] Alert history and acknowledgment
- [ ] AI anomaly detection (basic — statistical outlier detection)
- [ ] CSV data export
- [ ] Mobile-responsive dashboard

### Nice to Have (Week 11+)
- [ ] Natural language insights ("Your Unit 3 compressor used 23% more energy...")
- [ ] Predictive maintenance suggestions
- [ ] SMS/WhatsApp alerts
- [ ] Pre-configured IoT gateway image (Raspberry Pi)
- [ ] API for third-party integrations

---

## Open Questions For You

> [!IMPORTANT]
> Before we start building, I need your input on:

1. **Do you agree with Option A (build IoT natively in Django)?** Or do you feel strongly about keeping ThingsBoard in the picture?

2. **Cold chain as beachhead** — are you comfortable starting with temperature/humidity monitoring as our MVP use case, or do you have specific customer contacts in a different vertical?

3. **Hardware strategy** — for the MVP, are we asking pilot customers to bring their own sensors/gateways? Or are we providing a pre-configured kit? This affects the onboarding flow we design.

4. **Timeline** — are you working on this full-time, or alongside other commitments? This affects how aggressively we scope the MVP.

5. **Budget for infrastructure** — are you comfortable with ~$50-100/mo cloud costs during the pilot phase?
