# AIR BEE - System Design Document

## Document Information

- **Project Name:** AIR BEE
- **Category:** AI for Retail, Commerce & Market Intelligence
- **Version:** 1.0
- **Date:** February 15, 2026
- **Status:** Production-Grade Design

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [High-Level Architecture Diagram](#high-level-architecture-diagram)
3. [Component Architecture](#component-architecture)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Database Schema Overview](#database-schema-overview)
6. [AI/ML Model Architecture](#aiml-model-architecture)
7. [Multi-Tenant SaaS Architecture](#multi-tenant-saas-architecture)
8. [API Design Overview](#api-design-overview)
9. [Scalability Design](#scalability-design)
10. [Security Architecture](#security-architecture)
11. [Deployment Architecture](#deployment-architecture)
12. [Monitoring & Logging](#monitoring--logging)
13. [Future Scalability Considerations](#future-scalability-considerations)

---

## System Architecture Overview

AIR BEE is designed as a cloud-native, multi-tenant SaaS platform leveraging microservices architecture principles for scalability, maintainability, and resilience. The system is composed of four primary layers:

### Architecture Layers

**1. Presentation Layer**
- React-based single-page application (SPA) with TypeScript
- TailwindCSS for responsive, modern UI
- Real-time data visualization using Chart.js/Recharts
- Progressive Web App (PWA) capabilities for offline access

**2. Application Layer**
- RESTful API services built with Node.js/Express or Django REST Framework
- Authentication & authorization service
- Business logic services (booking, revenue, analytics)
- Background job processing for async operations
- WebSocket server for real-time updates

**3. Data Layer**
- PostgreSQL for transactional data with multi-tenant isolation
- Redis for caching and session management
- TimescaleDB extension for time-series data
- S3-compatible object storage for files and backups

**4. AI/ML Layer**
- Python-based ML services for forecasting and pricing
- LLM integration for AI Copilot (OpenAI API, Azure OpenAI, or self-hosted)
- Model training pipeline with MLflow for experiment tracking
- Feature store for ML feature management

### Design Principles

1. **Separation of Concerns:** Clear boundaries between presentation, business logic, data, and AI layers
2. **Scalability First:** Horizontal scaling capability at every layer
3. **Multi-Tenancy:** Complete data isolation with shared infrastructure
4. **API-First:** All functionality exposed through well-documented APIs
5. **Event-Driven:** Asynchronous processing for long-running operations
6. **Security by Design:** Zero-trust architecture with encryption everywhere
7. **Observability:** Comprehensive logging, metrics, and tracing
8. **Resilience:** Graceful degradation and fault tolerance

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Web App    │  │  Mobile App  │  │  Third-Party │                  │
│  │ (React + TS) │  │  (Future)    │  │  Integrations│                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   CDN / WAF     │
                    │  (CloudFlare)   │
                    └────────┬────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────────┐
│                        API GATEWAY LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  API Gateway (Kong / AWS API Gateway)                           │    │
│  │  - Rate Limiting  - Authentication  - Request Routing           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────▼─────────┐  ┌────▼──────────┐
│                │  │              │  │               │
│  APPLICATION SERVICES LAYER                         │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │         Core API Services (Node.js/Django)   │  │
│  │                                               │  │
│  │  ┌─────────────┐  ┌──────────────┐          │  │
│  │  │   Auth      │  │   Booking    │          │  │
│  │  │   Service   │  │   Service    │          │  │
│  │  └─────────────┘  └──────────────┘          │  │
│  │                                               │  │
│  │  ┌─────────────┐  ┌──────────────┐          │  │
│  │  │  Revenue    │  │  Analytics   │          │  │
│  │  │  Service    │  │  Service     │          │  │
│  │  └─────────────┘  └──────────────┘          │  │
│  │                                               │  │
│  │  ┌─────────────┐  ┌──────────────┐          │  │
│  │  │  Customer   │  │  Integration │          │  │
│  │  │  Service    │  │  Service     │          │  │
│  │  └─────────────┘  └──────────────┘          │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │      Background Job Processor (Bull/Celery) │  │
│  │  - Data Import  - Report Generation          │  │
│  │  - Email Notifications  - Model Training     │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │         WebSocket Server (Socket.io)         │  │
│  │  - Real-time Dashboard Updates               │  │
│  │  - Live Notifications                        │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐
│              │ │           │ │               │
│  AI/ML LAYER │ │ DATA LAYER│ │  CACHE LAYER  │
│              │ │           │ │               │
│ ┌──────────┐ │ │ ┌───────┐ │ │  ┌────────┐  │
│ │Forecasting│ │ │ │Postgres│ │ │  │ Redis  │  │
│ │  Engine  │ │ │ │  +     │ │ │  │        │  │
│ │ (Python) │ │ │ │Timescale│ │ │  │Session │  │
│ └──────────┘ │ │ └───────┘ │ │  │ Cache  │  │
│              │ │           │ │  └────────┘  │
│ ┌──────────┐ │ │ ┌───────┐ │ │              │
│ │ Pricing  │ │ │ │  S3   │ │ │              │
│ │  Engine  │ │ │ │Storage│ │ │              │
│ └──────────┘ │ │ └───────┘ │ │              │
│              │ │           │ │              │
│ ┌──────────┐ │ └───────────┘ └──────────────┘
│ │AI Copilot│ │
│ │   LLM    │ │
│ └──────────┘ │
│              │
│ ┌──────────┐ │
│ │  MLflow  │ │
│ │ Tracking │ │
│ └──────────┘ │
└──────────────┘

┌─────────────────────────────────────────────────┐
│         EXTERNAL INTEGRATIONS                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   PMS    │  │  Payment │  │   CRM    │      │
│  │ Systems  │  │ Gateways │  │ Systems  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘
```

---

## Component Architecture

### 3.1 Frontend Components


**Technology Stack:**
- React 18+ with TypeScript
- TailwindCSS for styling
- React Query for server state management
- Zustand/Redux for client state management
- Chart.js/Recharts for data visualization
- React Router for navigation
- Axios for HTTP requests

**Component Structure:**

```
src/
├── components/
│   ├── common/              # Reusable UI components
│   │   ├── Button/
│   │   ├── Card/
│   │   ├── Table/
│   │   ├── Chart/
│   │   └── Modal/
│   ├── layout/              # Layout components
│   │   ├── Header/
│   │   ├── Sidebar/
│   │   └── Footer/
│   └── features/            # Feature-specific components
│       ├── Dashboard/
│       ├── Booking/
│       ├── Revenue/
│       ├── Forecasting/
│       ├── Pricing/
│       ├── Customer/
│       └── Copilot/
├── hooks/                   # Custom React hooks
├── services/                # API service layer
├── store/                   # State management
├── utils/                   # Utility functions
├── types/                   # TypeScript type definitions
└── config/                  # Configuration files
```

**Key Frontend Features:**

1. **Dashboard Module**
   - Real-time metrics display
   - Customizable widget layout
   - Interactive charts with drill-down
   - Export functionality

2. **Booking Management**
   - Booking list with filters
   - Booking detail view
   - Bulk import interface
   - Status tracking

3. **Revenue Analytics**
   - Revenue trends visualization
   - Comparative analysis tools
   - Custom date range selection
   - Report generation

4. **Forecasting Interface**
   - Forecast visualization with confidence intervals
   - Model performance metrics
   - Manual adjustment controls
   - Scenario comparison

5. **Pricing Dashboard**
   - Price recommendation display
   - Competitor price tracking
   - Price elasticity charts
   - Simulation tools

6. **Customer Insights**
   - Segment visualization
   - Customer journey mapping
   - CLV analysis
   - Campaign recommendations

7. **AI Copilot Chat**
   - Conversational interface
   - Voice input support
   - Response visualization
   - Query history

### 3.2 Backend Services

**Technology Stack:**
- Node.js with Express.js OR Django with Django REST Framework
- TypeScript (for Node.js) / Python 3.11+ (for Django)
- JWT for authentication
- Bull (Node.js) or Celery (Django) for job queues
- Socket.io for WebSocket
- Prisma (Node.js) or Django ORM for database access

**Service Architecture:**


#### Authentication Service
**Responsibilities:**
- User registration and login
- JWT token generation and validation
- Multi-factor authentication (MFA)
- Password reset and recovery
- Session management
- OAuth integration (Google, Microsoft)

**Key Endpoints:**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/verify-mfa`

#### Booking Service
**Responsibilities:**
- CRUD operations for bookings
- Booking status management
- Data import from PMS systems
- Booking analytics aggregation
- Historical data management

**Key Endpoints:**
- `GET /api/v1/bookings`
- `GET /api/v1/bookings/:id`
- `POST /api/v1/bookings`
- `PUT /api/v1/bookings/:id`
- `DELETE /api/v1/bookings/:id`
- `POST /api/v1/bookings/import`
- `GET /api/v1/bookings/analytics`

#### Revenue Service
**Responsibilities:**
- Revenue calculation and aggregation
- RevPAR, ADR computation
- Revenue forecasting coordination
- Comparative analysis
- Report generation

**Key Endpoints:**
- `GET /api/v1/revenue/metrics`
- `GET /api/v1/revenue/trends`
- `GET /api/v1/revenue/comparison`
- `POST /api/v1/revenue/reports`
- `GET /api/v1/revenue/forecast`

#### Analytics Service
**Responsibilities:**
- Occupancy analytics
- Performance metrics calculation
- Custom report generation
- Data aggregation and transformation
- Dashboard data preparation

**Key Endpoints:**
- `GET /api/v1/analytics/occupancy`
- `GET /api/v1/analytics/performance`
- `POST /api/v1/analytics/custom-report`
- `GET /api/v1/analytics/dashboard`

#### Customer Service
**Responsibilities:**
- Customer segmentation
- CLV calculation
- Behavior analysis
- Campaign recommendations
- Guest profile management

**Key Endpoints:**
- `GET /api/v1/customers`
- `GET /api/v1/customers/:id`
- `GET /api/v1/customers/segments`
- `GET /api/v1/customers/insights`
- `GET /api/v1/customers/:id/clv`

#### Integration Service
**Responsibilities:**
- PMS system integration
- Third-party API management
- Data synchronization
- Webhook handling
- API key management

**Key Endpoints:**
- `POST /api/v1/integrations/pms/sync`
- `GET /api/v1/integrations/status`
- `POST /api/v1/integrations/webhooks`
- `GET /api/v1/integrations/api-keys`

### 3.3 AI/ML Services

**Technology Stack:**
- Python 3.11+
- FastAPI for ML service APIs
- Scikit-learn for traditional ML
- Prophet for time-series forecasting
- TensorFlow/PyTorch for deep learning
- LangChain for LLM orchestration
- MLflow for experiment tracking
- Pandas, NumPy for data processing

**Service Components:**


#### Forecasting Engine
**Responsibilities:**
- Demand forecasting using time-series models
- Model training and retraining
- Forecast accuracy evaluation
- Confidence interval calculation
- Exogenous variable integration

**Models:**
- ARIMA (AutoRegressive Integrated Moving Average)
- Prophet (Facebook's forecasting tool)
- LSTM (Long Short-Term Memory networks)
- Ensemble methods combining multiple models

**API Endpoints:**
- `POST /api/v1/ml/forecast/demand`
- `GET /api/v1/ml/forecast/accuracy`
- `POST /api/v1/ml/forecast/retrain`
- `GET /api/v1/ml/models/performance`

#### Pricing Engine
**Responsibilities:**
- Dynamic price recommendations
- Price elasticity analysis
- Competitor price analysis
- Revenue optimization
- A/B testing support

**Algorithms:**
- Reinforcement learning (Q-learning, DQN)
- Optimization algorithms (linear programming)
- Regression models for elasticity
- Rule-based constraints

**API Endpoints:**
- `POST /api/v1/ml/pricing/recommend`
- `GET /api/v1/ml/pricing/elasticity`
- `POST /api/v1/ml/pricing/simulate`
- `GET /api/v1/ml/pricing/performance`

#### Segmentation Engine
**Responsibilities:**
- Customer clustering
- Segment profiling
- Churn prediction
- CLV prediction
- Recommendation generation

**Algorithms:**
- K-means clustering
- DBSCAN for density-based clustering
- Random Forest for churn prediction
- XGBoost for CLV prediction

**API Endpoints:**
- `POST /api/v1/ml/segmentation/cluster`
- `GET /api/v1/ml/segmentation/profiles`
- `POST /api/v1/ml/segmentation/predict-churn`
- `GET /api/v1/ml/segmentation/clv`

#### AI Copilot Service
**Responsibilities:**
- Natural language query processing
- Context-aware response generation
- Data retrieval and aggregation
- Visualization generation
- Conversation management

**Components:**
- LLM integration (OpenAI GPT-4, Azure OpenAI)
- Vector database for RAG (Pinecone, Weaviate)
- Query parser and intent classifier
- Response generator
- Context manager

**API Endpoints:**
- `POST /api/v1/copilot/query`
- `GET /api/v1/copilot/history`
- `POST /api/v1/copilot/feedback`
- `DELETE /api/v1/copilot/session`

---

## Data Flow Architecture

### 4.1 Data Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   PMS    │  │  Manual  │  │   CSV    │  │  Webhook │   │
│  │   API    │  │  Entry   │  │  Upload  │  │  Events  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                          │
                ┌─────────▼─────────┐
                │  API Gateway      │
                │  - Validation     │
                │  - Rate Limiting  │
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────┐
                │ Integration       │
                │ Service           │
                │ - Transform       │
                │ - Validate        │
                │ - Enrich          │
                └─────────┬─────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼────────┐ ┌─────▼──────┐ ┌───────▼────────┐
│  Message Queue │ │ PostgreSQL │ │  Event Stream  │
│  (Bull/Celery) │ │  (Direct)  │ │  (Future)      │
└───────┬────────┘ └────────────┘ └────────────────┘
        │
        │ Async Processing
        │
┌───────▼────────────────────────────────────────┐
│         Background Job Processor               │
│  ┌──────────────┐  ┌──────────────┐           │
│  │ Data         │  │ Data         │           │
│  │ Validation   │  │ Enrichment   │           │
│  └──────┬───────┘  └──────┬───────┘           │
│         │                 │                    │
│  ┌──────▼─────────────────▼───────┐           │
│  │    Write to PostgreSQL         │           │
│  └──────┬─────────────────────────┘           │
│         │                                      │
│  ┌──────▼─────────────────────────┐           │
│  │  Trigger Analytics Update      │           │
│  └────────────────────────────────┘           │
└────────────────────────────────────────────────┘
```

### 4.2 Demand Forecasting Workflow


```
┌─────────────────────────────────────────────────────────────┐
│                  FORECASTING PIPELINE                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Data Collection
┌──────────────────────────────────────┐
│  Historical Booking Data             │
│  - Daily occupancy (2+ years)        │
│  - Room types                        │
│  - Booking patterns                  │
│  - Cancellation rates                │
└──────────────┬───────────────────────┘
               │
Step 2: Feature Engineering
┌──────────────▼───────────────────────┐
│  Feature Extraction                  │
│  - Seasonality (day, week, month)    │
│  - Trends (linear, polynomial)       │
│  - Lag features (7, 14, 30 days)     │
│  - Rolling statistics (mean, std)    │
│  - Holiday indicators                │
│  - Local events                      │
│  - Weather data (optional)           │
└──────────────┬───────────────────────┘
               │
Step 3: Model Training (Monthly)
┌──────────────▼───────────────────────┐
│  Parallel Model Training             │
│  ┌────────────┐  ┌────────────┐     │
│  │   ARIMA    │  │  Prophet   │     │
│  └─────┬──────┘  └─────┬──────┘     │
│        │               │             │
│  ┌─────▼──────┐  ┌─────▼──────┐     │
│  │    LSTM    │  │  Ensemble  │     │
│  └─────┬──────┘  └─────┬──────┘     │
│        └───────┬───────┘             │
└────────────────┼─────────────────────┘
                 │
Step 4: Model Evaluation
┌────────────────▼─────────────────────┐
│  Cross-Validation & Metrics          │
│  - MAPE (Mean Absolute % Error)      │
│  - RMSE (Root Mean Squared Error)    │
│  - MAE (Mean Absolute Error)         │
│  - Select best performing model      │
└────────────────┬─────────────────────┘
                 │
Step 5: Prediction
┌────────────────▼─────────────────────┐
│  Generate Forecasts                  │
│  - 30-day forecast                   │
│  - 60-day forecast                   │
│  - 90-day forecast                   │
│  - Confidence intervals (80%, 95%)   │
└────────────────┬─────────────────────┘
                 │
Step 6: Storage & Serving
┌────────────────▼─────────────────────┐
│  Store Results                       │
│  - PostgreSQL (forecasts)            │
│  - Redis (cache for API)             │
│  - MLflow (model metadata)           │
└────────────────┬─────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │  API Response │
         │  to Frontend  │
         └───────────────┘
```

**Forecasting Algorithm Details:**

**ARIMA Model:**
```python
# Pseudocode
def train_arima(data, order=(p, d, q)):
    # p: autoregressive order
    # d: differencing order
    # q: moving average order
    
    # Auto-select parameters using AIC
    model = auto_arima(data, 
                       seasonal=True, 
                       m=7,  # weekly seasonality
                       stepwise=True)
    
    # Fit model
    model.fit(data)
    
    # Generate forecast
    forecast = model.predict(n_periods=90)
    confidence_intervals = model.predict_intervals(n_periods=90)
    
    return forecast, confidence_intervals
```

**Prophet Model:**
```python
# Pseudocode
def train_prophet(data, holidays, events):
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        holidays=holidays
    )
    
    # Add custom seasonality
    model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
    
    # Add external regressors
    model.add_regressor('local_events')
    model.add_regressor('competitor_pricing')
    
    # Fit model
    model.fit(data)
    
    # Generate forecast
    future = model.make_future_dataframe(periods=90)
    forecast = model.predict(future)
    
    return forecast
```

**LSTM Model:**
```python
# Pseudocode
def train_lstm(data, sequence_length=30):
    # Prepare sequences
    X, y = create_sequences(data, sequence_length)
    
    # Build model
    model = Sequential([
        LSTM(128, return_sequences=True, input_shape=(sequence_length, features)),
        Dropout(0.2),
        LSTM(64, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mse')
    
    # Train with early stopping
    model.fit(X, y, epochs=100, batch_size=32, 
              validation_split=0.2,
              callbacks=[EarlyStopping(patience=10)])
    
    # Generate forecast
    forecast = recursive_forecast(model, last_sequence, n_periods=90)
    
    return forecast
```

### 4.3 Dynamic Pricing Logic


```
┌─────────────────────────────────────────────────────────────┐
│              DYNAMIC PRICING PIPELINE                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Input Data Collection
┌──────────────────────────────────────┐
│  Pricing Inputs                      │
│  - Current occupancy rate            │
│  - Demand forecast                   │
│  - Historical pricing performance    │
│  - Competitor prices                 │
│  - Booking pace                      │
│  - Days until arrival                │
│  - Room type availability            │
│  - Seasonality factors               │
└──────────────┬───────────────────────┘
               │
Step 2: Price Elasticity Calculation
┌──────────────▼───────────────────────┐
│  Elasticity Model                    │
│  E = % Change in Demand /            │
│      % Change in Price               │
│                                      │
│  - Train regression model            │
│  - Segment-specific elasticity       │
│  - Time-based elasticity             │
└──────────────┬───────────────────────┘
               │
Step 3: Optimization Engine
┌──────────────▼───────────────────────┐
│  Revenue Optimization                │
│                                      │
│  Objective: Maximize Revenue         │
│  Revenue = Price × Occupancy         │
│                                      │
│  Constraints:                        │
│  - Min price threshold               │
│  - Max price threshold               │
│  - Competitor price range            │
│  - Brand positioning                 │
│  - Historical rate parity            │
└──────────────┬───────────────────────┘
               │
Step 4: Price Recommendation
┌──────────────▼───────────────────────┐
│  Generate Recommendations            │
│  - Optimal price per room type       │
│  - Expected occupancy impact         │
│  - Revenue projection                │
│  - Confidence score                  │
│  - Alternative scenarios             │
└──────────────┬───────────────────────┘
               │
Step 5: Human Review (Optional)
┌──────────────▼───────────────────────┐
│  Revenue Manager Review              │
│  - Accept recommendation             │
│  - Adjust with constraints           │
│  - Override with manual price        │
└──────────────┬───────────────────────┘
               │
Step 6: Implementation & Tracking
┌──────────────▼───────────────────────┐
│  Apply Pricing & Monitor             │
│  - Update PMS system                 │
│  - Track booking response            │
│  - Measure actual vs predicted       │
│  - Feed back to model                │
└──────────────────────────────────────┘
```

**Pricing Algorithm:**

```python
# Pseudocode for Dynamic Pricing
def calculate_optimal_price(
    base_price,
    demand_forecast,
    current_occupancy,
    competitor_prices,
    days_until_arrival,
    elasticity
):
    # 1. Calculate demand multiplier
    if demand_forecast > 0.85:  # High demand
        demand_multiplier = 1.2
    elif demand_forecast > 0.70:  # Medium demand
        demand_multiplier = 1.0
    else:  # Low demand
        demand_multiplier = 0.85
    
    # 2. Calculate urgency multiplier
    if days_until_arrival < 7:
        urgency_multiplier = 1.15  # Last-minute premium
    elif days_until_arrival < 30:
        urgency_multiplier = 1.0
    else:
        urgency_multiplier = 0.95  # Early bird discount
    
    # 3. Calculate competitive position
    avg_competitor_price = mean(competitor_prices)
    competitive_multiplier = 0.95 if avg_competitor_price < base_price else 1.05
    
    # 4. Calculate initial recommended price
    recommended_price = (
        base_price * 
        demand_multiplier * 
        urgency_multiplier * 
        competitive_multiplier
    )
    
    # 5. Apply constraints
    min_price = base_price * 0.7  # Never go below 70% of base
    max_price = base_price * 1.5  # Never exceed 150% of base
    
    recommended_price = clamp(recommended_price, min_price, max_price)
    
    # 6. Calculate expected impact
    price_change_pct = (recommended_price - base_price) / base_price
    demand_change_pct = price_change_pct * elasticity
    expected_occupancy = current_occupancy * (1 + demand_change_pct)
    expected_revenue = recommended_price * expected_occupancy
    
    return {
        'recommended_price': recommended_price,
        'expected_occupancy': expected_occupancy,
        'expected_revenue': expected_revenue,
        'confidence': calculate_confidence_score(),
        'factors': {
            'demand': demand_multiplier,
            'urgency': urgency_multiplier,
            'competitive': competitive_multiplier
        }
    }
```

### 4.4 Revenue Prediction Workflow


```
Revenue Prediction = Demand Forecast × Optimal Price × Room Inventory

┌──────────────────────────────────────┐
│  Input: Demand Forecast              │
│  (from Forecasting Engine)           │
│  - Expected occupancy per day        │
│  - Confidence intervals              │
└──────────────┬───────────────────────┘
               │
               ├──────────────────────────┐
               │                          │
┌──────────────▼───────────────┐  ┌──────▼──────────────────┐
│  Input: Pricing Strategy     │  │  Input: Inventory       │
│  (from Pricing Engine)       │  │  - Total rooms          │
│  - Recommended prices        │  │  - Room types           │
│  - Price scenarios           │  │  - Availability         │
└──────────────┬───────────────┘  └──────┬──────────────────┘
               │                          │
               └──────────┬───────────────┘
                          │
               ┌──────────▼───────────────┐
               │  Revenue Calculation     │
               │                          │
               │  For each day:           │
               │  Revenue = Σ(            │
               │    Room_Type_i *         │
               │    Occupancy_i *         │
               │    Price_i               │
               │  )                       │
               └──────────┬───────────────┘
                          │
               ┌──────────▼───────────────┐
               │  Aggregate Metrics       │
               │  - Total revenue         │
               │  - RevPAR                │
               │  - ADR                   │
               │  - Occupancy %           │
               │  - Revenue by segment    │
               └──────────┬───────────────┘
                          │
               ┌──────────▼───────────────┐
               │  Scenario Analysis       │
               │  - Best case             │
               │  - Expected case         │
               │  - Worst case            │
               │  - Custom scenarios      │
               └──────────┬───────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  Dashboard    │
                  │  Display      │
                  └───────────────┘
```

### 4.5 Customer Segmentation Logic

```
┌─────────────────────────────────────────────────────────────┐
│           CUSTOMER SEGMENTATION PIPELINE                     │
└─────────────────────────────────────────────────────────────┘

Step 1: Feature Engineering
┌──────────────────────────────────────┐
│  Customer Features                   │
│  - Booking frequency                 │
│  - Average booking value             │
│  - Lead time (days before arrival)   │
│  - Length of stay                    │
│  - Room type preference              │
│  - Booking channel                   │
│  - Cancellation rate                 │
│  - Seasonality preference            │
│  - Total lifetime value              │
│  - Recency (days since last booking) │
└──────────────┬───────────────────────┘
               │
Step 2: Feature Scaling
┌──────────────▼───────────────────────┐
│  Normalization                       │
│  - StandardScaler for numeric        │
│  - One-hot encoding for categorical  │
│  - Handle missing values             │
└──────────────┬───────────────────────┘
               │
Step 3: Clustering
┌──────────────▼───────────────────────┐
│  K-Means Clustering                  │
│  - Determine optimal k (elbow method)│
│  - Typical segments: 4-6             │
│                                      │
│  Example Segments:                   │
│  1. High-Value Frequent (VIP)        │
│  2. Business Travelers               │
│  3. Leisure Families                 │
│  4. Budget Conscious                 │
│  5. Last-Minute Bookers              │
│  6. Long-Stay Guests                 │
└──────────────┬───────────────────────┘
               │
Step 4: Segment Profiling
┌──────────────▼───────────────────────┐
│  Profile Each Segment                │
│  - Average metrics                   │
│  - Behavioral patterns               │
│  - Revenue contribution              │
│  - Growth trends                     │
│  - Churn risk                        │
└──────────────┬───────────────────────┘
               │
Step 5: CLV Prediction
┌──────────────▼───────────────────────┐
│  Customer Lifetime Value             │
│  CLV = Σ(Revenue_t / (1+d)^t)       │
│                                      │
│  Using XGBoost Regression:           │
│  - Historical revenue                │
│  - Booking patterns                  │
│  - Segment characteristics           │
│  - Predict future value              │
└──────────────┬───────────────────────┘
               │
Step 6: Actionable Insights
┌──────────────▼───────────────────────┐
│  Generate Recommendations            │
│  - Targeted marketing campaigns      │
│  - Personalized offers               │
│  - Retention strategies              │
│  - Upsell opportunities              │
└──────────────────────────────────────┘
```

**Segmentation Algorithm:**

```python
# Pseudocode
def segment_customers(customer_data):
    # 1. Feature engineering
    features = engineer_features(customer_data)
    
    # 2. Scaling
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    # 3. Determine optimal clusters
    inertias = []
    K_range = range(2, 11)
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42)
        kmeans.fit(scaled_features)
        inertias.append(kmeans.inertia_)
    
    optimal_k = find_elbow_point(inertias)  # Typically 4-6
    
    # 4. Final clustering
    kmeans = KMeans(n_clusters=optimal_k, random_state=42)
    segments = kmeans.fit_predict(scaled_features)
    
    # 5. Profile segments
    profiles = []
    for segment_id in range(optimal_k):
        segment_customers = customer_data[segments == segment_id]
        profile = {
            'segment_id': segment_id,
            'size': len(segment_customers),
            'avg_booking_value': segment_customers['booking_value'].mean(),
            'avg_frequency': segment_customers['frequency'].mean(),
            'total_revenue': segment_customers['total_revenue'].sum(),
            'characteristics': describe_segment(segment_customers)
        }
        profiles.append(profile)
    
    return segments, profiles
```

### 4.6 AI Copilot Query Pipeline


```
┌─────────────────────────────────────────────────────────────┐
│              AI COPILOT ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────┘

User Query: "What is our occupancy forecast for next month?"

Step 1: Query Reception
┌──────────────────────────────────────┐
│  Frontend Chat Interface             │
│  - Capture user query                │
│  - Maintain conversation context     │
│  - Send to Copilot API               │
└──────────────┬───────────────────────┘
               │
Step 2: Intent Classification
┌──────────────▼───────────────────────┐
│  NLP Intent Classifier               │
│  - Parse query                       │
│  - Identify intent type:             │
│    * Forecasting query               │
│    * Revenue query                   │
│    * Customer insights               │
│    * Operational metrics             │
│    * Comparative analysis            │
│  - Extract entities (dates, metrics) │
└──────────────┬───────────────────────┘
               │
Step 3: Context Retrieval (RAG)
┌──────────────▼───────────────────────┐
│  Retrieval-Augmented Generation      │
│  ┌────────────────────────────────┐  │
│  │  Vector Database               │  │
│  │  - Historical queries          │  │
│  │  - Documentation               │  │
│  │  - Business context            │  │
│  └────────────┬───────────────────┘  │
│               │                       │
│  ┌────────────▼───────────────────┐  │
│  │  Semantic Search               │  │
│  │  - Find relevant context       │  │
│  │  - Retrieve similar queries    │  │
│  └────────────────────────────────┘  │
└──────────────┬───────────────────────┘
               │
Step 4: Data Query Generation
┌──────────────▼───────────────────────┐
│  Query Translator                    │
│  - Convert NL to SQL/API calls       │
│  - Apply tenant filters              │
│  - Apply user permissions            │
│                                      │
│  Example:                            │
│  "next month occupancy" →            │
│  SELECT forecast_value               │
│  FROM occupancy_forecasts            │
│  WHERE tenant_id = ?                 │
│    AND date >= '2026-03-01'          │
│    AND date <= '2026-03-31'          │
└──────────────┬───────────────────────┘
               │
Step 5: Data Retrieval
┌──────────────▼───────────────────────┐
│  Execute Queries                     │
│  - Query PostgreSQL                  │
│  - Call ML services if needed        │
│  - Aggregate results                 │
│  - Format data                       │
└──────────────┬───────────────────────┘
               │
Step 6: Response Generation
┌──────────────▼───────────────────────┐
│  LLM Response Generator              │
│  - Construct prompt with:            │
│    * User query                      │
│    * Retrieved data                  │
│    * Context                         │
│    * Conversation history            │
│  - Generate natural language response│
│  - Include data citations            │
└──────────────┬───────────────────────┘
               │
Step 7: Visualization (if applicable)
┌──────────────▼───────────────────────┐
│  Chart Generation                    │
│  - Determine chart type              │
│  - Format data for visualization     │
│  - Generate chart config             │
└──────────────┬───────────────────────┘
               │
Step 8: Response Delivery
┌──────────────▼───────────────────────┐
│  API Response                        │
│  {                                   │
│    "response": "Based on...",        │
│    "data": {...},                    │
│    "visualization": {...},           │
│    "sources": [...],                 │
│    "confidence": 0.92                │
│  }                                   │
└──────────────┬───────────────────────┘
               │
               ▼
       ┌───────────────┐
       │  Display in   │
       │  Chat UI      │
       └───────────────┘
```

**Copilot Implementation:**

```python
# Pseudocode for AI Copilot
class AICopilot:
    def __init__(self, llm_client, vector_db, database):
        self.llm = llm_client
        self.vector_db = vector_db
        self.db = database
        
    async def process_query(self, query, user_context, conversation_history):
        # 1. Classify intent
        intent = await self.classify_intent(query)
        
        # 2. Extract entities
        entities = self.extract_entities(query)
        
        # 3. Retrieve relevant context (RAG)
        context = await self.vector_db.similarity_search(
            query, 
            k=5,
            filter={'tenant_id': user_context.tenant_id}
        )
        
        # 4. Generate data query
        data_query = self.generate_data_query(intent, entities, user_context)
        
        # 5. Execute query
        data = await self.db.execute(data_query)
        
        # 6. Construct LLM prompt
        prompt = f"""
        You are an AI assistant for AIR BEE, a hotel management platform.
        
        User Question: {query}
        
        Relevant Context: {context}
        
        Data Retrieved: {data}
        
        Conversation History: {conversation_history}
        
        Provide a clear, concise answer with specific numbers and insights.
        If showing trends, suggest visualizations.
        Always cite data sources.
        """
        
        # 7. Generate response
        response = await self.llm.generate(
            prompt,
            temperature=0.3,  # Lower for factual responses
            max_tokens=500
        )
        
        # 8. Determine if visualization needed
        viz_config = None
        if self.should_visualize(intent, data):
            viz_config = self.generate_visualization_config(intent, data)
        
        return {
            'response': response,
            'data': data,
            'visualization': viz_config,
            'sources': self.extract_sources(data),
            'confidence': self.calculate_confidence(intent, data)
        }
    
    def classify_intent(self, query):
        # Use fine-tuned classifier or LLM
        intents = [
            'forecasting', 'revenue', 'occupancy', 
            'pricing', 'customer', 'comparison'
        ]
        # Return classified intent
        pass
    
    def extract_entities(self, query):
        # Extract dates, metrics, room types, etc.
        # Using NER or LLM
        pass
```

---

## Database Schema Overview

### 5.1 Core Tables


```sql
-- Multi-Tenant Architecture: All tables include tenant_id

-- Tenants (Properties/Hotels)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    subscription_tier VARCHAR(50) NOT NULL, -- basic, pro, enterprise
    status VARCHAR(50) DEFAULT 'active', -- active, suspended, cancelled
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) NOT NULL, -- super_admin, property_admin, revenue_manager, etc.
    is_active BOOLEAN DEFAULT true,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret VARCHAR(255),
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User-Tenant Association (Many-to-Many)
CREATE TABLE user_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, tenant_id)
);

-- Room Types
CREATE TABLE room_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    base_price DECIMAL(10, 2) NOT NULL,
    capacity INT NOT NULL,
    total_rooms INT NOT NULL,
    amenities JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Bookings
CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    room_type_id UUID REFERENCES room_types(id),
    booking_reference VARCHAR(50) UNIQUE NOT NULL,
    guest_name VARCHAR(255) NOT NULL,
    guest_email VARCHAR(255),
    guest_phone VARCHAR(50),
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    booking_date TIMESTAMP NOT NULL,
    num_guests INT NOT NULL,
    num_rooms INT DEFAULT 1,
    room_rate DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    booking_source VARCHAR(100), -- direct, ota, agent, etc.
    status VARCHAR(50) NOT NULL, -- confirmed, cancelled, no_show, completed
    special_requests TEXT,
    cancellation_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bookings_tenant_dates ON bookings(tenant_id, check_in_date, check_out_date);
CREATE INDEX idx_bookings_status ON bookings(tenant_id, status);

-- Daily Occupancy (Time-Series Data)
CREATE TABLE daily_occupancy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    room_type_id UUID REFERENCES room_types(id),
    date DATE NOT NULL,
    total_rooms INT NOT NULL,
    occupied_rooms INT NOT NULL,
    occupancy_rate DECIMAL(5, 2) NOT NULL,
    revenue DECIMAL(10, 2) NOT NULL,
    adr DECIMAL(10, 2), -- Average Daily Rate
    revpar DECIMAL(10, 2), -- Revenue Per Available Room
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, room_type_id, date)
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('daily_occupancy', 'date');

CREATE INDEX idx_daily_occupancy_tenant_date ON daily_occupancy(tenant_id, date DESC);

-- Demand Forecasts
CREATE TABLE demand_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    room_type_id UUID REFERENCES room_types(id),
    forecast_date DATE NOT NULL,
    target_date DATE NOT NULL,
    model_name VARCHAR(100) NOT NULL, -- arima, prophet, lstm, ensemble
    model_version VARCHAR(50),
    predicted_occupancy DECIMAL(5, 2) NOT NULL,
    confidence_lower DECIMAL(5, 2),
    confidence_upper DECIMAL(5, 2),
    confidence_level DECIMAL(3, 2) DEFAULT 0.95,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, room_type_id, target_date, model_name, forecast_date)
);

CREATE INDEX idx_forecasts_tenant_target ON demand_forecasts(tenant_id, target_date);

-- Price Recommendations
CREATE TABLE price_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    room_type_id UUID REFERENCES room_types(id),
    target_date DATE NOT NULL,
    current_price DECIMAL(10, 2) NOT NULL,
    recommended_price DECIMAL(10, 2) NOT NULL,
    expected_occupancy DECIMAL(5, 2),
    expected_revenue DECIMAL(10, 2),
    confidence_score DECIMAL(3, 2),
    factors JSONB, -- demand, urgency, competitive, etc.
    status VARCHAR(50) DEFAULT 'pending', -- pending, accepted, rejected, applied
    applied_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_price_recs_tenant_date ON price_recommendations(tenant_id, target_date);

-- Customer Segments
CREATE TABLE customer_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    segment_name VARCHAR(100) NOT NULL,
    description TEXT,
    characteristics JSONB,
    size INT,
    avg_booking_value DECIMAL(10, 2),
    total_revenue DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, segment_name)
);

-- Customer Profiles
CREATE TABLE customer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(50),
    segment_id UUID REFERENCES customer_segments(id),
    total_bookings INT DEFAULT 0,
    total_revenue DECIMAL(10, 2) DEFAULT 0,
    avg_booking_value DECIMAL(10, 2),
    last_booking_date DATE,
    predicted_clv DECIMAL(10, 2), -- Customer Lifetime Value
    churn_probability DECIMAL(3, 2),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE INDEX idx_customer_segment ON customer_profiles(tenant_id, segment_id);

-- ML Models Registry
CREATE TABLE ml_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL, -- forecasting, pricing, segmentation
    version VARCHAR(50) NOT NULL,
    algorithm VARCHAR(100),
    parameters JSONB,
    metrics JSONB, -- accuracy, mape, rmse, etc.
    training_date TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- active, archived, testing
    artifact_path VARCHAR(500), -- S3 path to model file
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ml_models_tenant_type ON ml_models(tenant_id, model_type, status);

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant_created ON audit_logs(tenant_id, created_at DESC);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    permissions JSONB DEFAULT '[]',
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Copilot Conversations
CREATE TABLE copilot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    session_id UUID NOT NULL,
    query TEXT NOT NULL,
    intent VARCHAR(100),
    response TEXT,
    data_sources JSONB,
    feedback VARCHAR(50), -- positive, negative, neutral
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_copilot_session ON copilot_conversations(session_id, created_at);
```

### 5.2 Database Optimization Strategies


**Indexing Strategy:**
- B-tree indexes on foreign keys and frequently queried columns
- Composite indexes on (tenant_id, date) for time-series queries
- GIN indexes on JSONB columns for flexible querying
- Partial indexes for active records only

**Partitioning:**
- Partition `bookings` table by check_in_date (monthly partitions)
- Partition `daily_occupancy` using TimescaleDB automatic partitioning
- Partition `audit_logs` by created_at (monthly partitions)

**Caching Strategy:**
- Redis cache for frequently accessed data (dashboard metrics, forecasts)
- Cache TTL: 5 minutes for real-time data, 1 hour for historical data
- Cache invalidation on data updates

**Query Optimization:**
- Use materialized views for complex aggregations
- Implement read replicas for analytics queries
- Use connection pooling (PgBouncer)
- Implement query result caching

---

## AI/ML Model Architecture

### 6.1 Model Training Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                  ML TRAINING PIPELINE                        │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│  Scheduled Trigger (Monthly)         │
│  OR Manual Trigger                   │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Data Extraction                     │
│  - Query PostgreSQL                  │
│  - Extract features                  │
│  - Export to training dataset        │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Data Preprocessing                  │
│  - Handle missing values             │
│  - Feature engineering               │
│  - Train/validation/test split       │
│  - Feature scaling                   │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Model Training (MLflow)             │
│  - Train multiple models             │
│  - Hyperparameter tuning             │
│  - Cross-validation                  │
│  - Log metrics and artifacts         │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Model Evaluation                    │
│  - Calculate metrics                 │
│  - Compare with baseline             │
│  - Validate on test set              │
└──────────────┬───────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│  Meets       │  │  Does Not Meet  │
│  Threshold?  │  │  Threshold      │
│  (Yes)       │  │  (No)           │
└───────┬──────┘  └──┬──────────────┘
        │            │
        │            ▼
        │     ┌──────────────┐
        │     │  Alert Team  │
        │     │  Keep Old    │
        │     │  Model       │
        │     └──────────────┘
        │
┌───────▼──────────────────────────────┐
│  Model Registration                  │
│  - Save to MLflow registry           │
│  - Upload to S3                      │
│  - Update database                   │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Model Deployment                    │
│  - Load into prediction service      │
│  - A/B test with old model           │
│  - Monitor performance               │
└──────────────────────────────────────┘
```

### 6.2 Model Serving Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  MODEL SERVING LAYER                         │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│  API Request                         │
│  POST /api/v1/ml/forecast/demand     │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  ML Service (FastAPI)                │
│  - Validate request                  │
│  - Extract features                  │
│  - Check cache                       │
└──────────────┬───────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│  Cache Hit?  │  │  Cache Miss     │
│  (Redis)     │  │                 │
└───────┬──────┘  └──┬──────────────┘
        │            │
        │     ┌──────▼──────────────┐
        │     │  Load Model         │
        │     │  - From memory      │
        │     │  - Or from S3       │
        │     └──────┬──────────────┘
        │            │
        │     ┌──────▼──────────────┐
        │     │  Run Inference      │
        │     │  - Preprocess       │
        │     │  - Predict          │
        │     │  - Post-process     │
        │     └──────┬──────────────┘
        │            │
        │     ┌──────▼──────────────┐
        │     │  Cache Result       │
        │     │  (Redis, 1hr TTL)   │
        │     └──────┬──────────────┘
        │            │
        └────────────┘
                     │
┌────────────────────▼─────────────────┐
│  Return Prediction                   │
│  - Forecast values                   │
│  - Confidence intervals              │
│  - Model metadata                    │
└──────────────────────────────────────┘
```

### 6.3 Model Monitoring

**Metrics Tracked:**
- Prediction accuracy (MAPE, RMSE, MAE)
- Prediction latency (p50, p95, p99)
- Model drift detection
- Data drift detection
- Feature importance changes
- Error rates and types

**Monitoring Tools:**
- MLflow for experiment tracking
- Prometheus for metrics collection
- Grafana for visualization
- Custom dashboards for business metrics

**Alerting:**
- Alert when accuracy drops below threshold (85%)
- Alert on high prediction latency (>2s)
- Alert on data quality issues
- Alert on model serving errors

---

## Multi-Tenant SaaS Architecture

### 7.1 Tenant Isolation Strategy

**Database-Level Isolation:**
```
Strategy: Shared Database, Shared Schema with tenant_id

Pros:
- Cost-effective for large number of tenants
- Easy to maintain and upgrade
- Efficient resource utilization

Cons:
- Requires careful query filtering
- Risk of data leakage if not implemented correctly

Implementation:
- Every table includes tenant_id column
- Row-Level Security (RLS) policies in PostgreSQL
- Application-level tenant context
- Middleware to inject tenant_id in all queries
```

**PostgreSQL Row-Level Security:**
```sql
-- Enable RLS on all tenant tables
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

-- Create policy for tenant isolation
CREATE POLICY tenant_isolation_policy ON bookings
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context in application
SET app.current_tenant = '<tenant_uuid>';
```

### 7.2 Tenant Context Management


**Node.js/Express Implementation:**
```javascript
// Middleware to extract and set tenant context
const tenantMiddleware = async (req, res, next) => {
    try {
        // Extract tenant from JWT token or subdomain
        const token = req.headers.authorization?.split(' ')[1];
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        
        // Get tenant from user-tenant association
        const userTenant = await db.query(
            'SELECT tenant_id FROM user_tenants WHERE user_id = $1',
            [decoded.userId]
        );
        
        if (!userTenant.rows[0]) {
            return res.status(403).json({ error: 'No tenant access' });
        }
        
        // Set tenant context
        req.tenantId = userTenant.rows[0].tenant_id;
        
        // Set PostgreSQL session variable
        await db.query(
            "SET app.current_tenant = $1",
            [req.tenantId]
        );
        
        next();
    } catch (error) {
        res.status(401).json({ error: 'Unauthorized' });
    }
};

// Apply to all routes
app.use('/api', tenantMiddleware);
```

**Django Implementation:**
```python
# Middleware for tenant context
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Extract tenant from JWT
        token = request.headers.get('Authorization', '').split(' ')[1]
        payload = jwt.decode(token, settings.SECRET_KEY)
        
        # Get tenant from user
        user_tenant = UserTenant.objects.get(user_id=payload['user_id'])
        request.tenant_id = user_tenant.tenant_id
        
        # Set PostgreSQL session variable
        with connection.cursor() as cursor:
            cursor.execute(
                "SET app.current_tenant = %s",
                [str(request.tenant_id)]
            )
        
        response = self.get_response(request)
        return response

# Custom manager for automatic tenant filtering
class TenantManager(models.Manager):
    def get_queryset(self):
        # Automatically filter by tenant
        return super().get_queryset().filter(
            tenant_id=get_current_tenant_id()
        )
```

### 7.3 Subscription & Billing Management

**Subscription Tiers:**
```javascript
const SUBSCRIPTION_TIERS = {
    basic: {
        name: 'Basic',
        price: 99,
        features: {
            max_properties: 1,
            max_users: 5,
            forecasting: true,
            dynamic_pricing: false,
            ai_copilot: false,
            api_access: false,
            support: 'email'
        }
    },
    pro: {
        name: 'Professional',
        price: 299,
        features: {
            max_properties: 5,
            max_users: 20,
            forecasting: true,
            dynamic_pricing: true,
            ai_copilot: true,
            api_access: true,
            support: 'priority'
        }
    },
    enterprise: {
        name: 'Enterprise',
        price: 'custom',
        features: {
            max_properties: 'unlimited',
            max_users: 'unlimited',
            forecasting: true,
            dynamic_pricing: true,
            ai_copilot: true,
            api_access: true,
            support: 'dedicated',
            custom_integrations: true,
            white_label: true
        }
    }
};
```

**Feature Gating:**
```javascript
// Middleware to check feature access
const featureGate = (feature) => {
    return async (req, res, next) => {
        const tenant = await Tenant.findById(req.tenantId);
        const tier = SUBSCRIPTION_TIERS[tenant.subscription_tier];
        
        if (!tier.features[feature]) {
            return res.status(403).json({
                error: 'Feature not available in your plan',
                upgrade_url: '/upgrade'
            });
        }
        
        next();
    };
};

// Apply to routes
app.post('/api/v1/ml/pricing/recommend', 
    tenantMiddleware,
    featureGate('dynamic_pricing'),
    pricingController.recommend
);
```

---

## API Design Overview

### 8.1 RESTful API Structure

**Base URL:** `https://api.airbee.com/v1`

**Authentication:** JWT Bearer Token

**Standard Response Format:**
```json
{
    "success": true,
    "data": { ... },
    "meta": {
        "timestamp": "2026-02-15T10:30:00Z",
        "request_id": "req_abc123"
    },
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 100,
        "total_pages": 5
    }
}
```

**Error Response Format:**
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid date format",
        "details": {
            "field": "check_in_date",
            "expected": "YYYY-MM-DD"
        }
    },
    "meta": {
        "timestamp": "2026-02-15T10:30:00Z",
        "request_id": "req_abc123"
    }
}
```

### 8.2 Key API Endpoints

**Authentication:**
```
POST   /auth/register
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout
POST   /auth/forgot-password
POST   /auth/reset-password
```

**Bookings:**
```
GET    /bookings                    # List bookings
GET    /bookings/:id                # Get booking details
POST   /bookings                    # Create booking
PUT    /bookings/:id                # Update booking
DELETE /bookings/:id                # Cancel booking
POST   /bookings/import             # Bulk import
GET    /bookings/analytics          # Booking analytics
```

**Revenue:**
```
GET    /revenue/metrics             # Current metrics
GET    /revenue/trends              # Historical trends
GET    /revenue/comparison          # Period comparison
POST   /revenue/reports             # Generate report
GET    /revenue/forecast            # Revenue forecast
```

**Forecasting:**
```
POST   /ml/forecast/demand          # Get demand forecast
GET    /ml/forecast/accuracy        # Model accuracy
POST   /ml/forecast/retrain         # Trigger retraining
GET    /ml/models/performance       # Model metrics
```

**Pricing:**
```
POST   /ml/pricing/recommend        # Get price recommendation
GET    /ml/pricing/elasticity       # Price elasticity
POST   /ml/pricing/simulate         # Simulate scenarios
GET    /ml/pricing/performance      # Pricing performance
```

**Customers:**
```
GET    /customers                   # List customers
GET    /customers/:id               # Customer details
GET    /customers/segments          # Segment analysis
GET    /customers/insights          # Behavior insights
GET    /customers/:id/clv           # Customer lifetime value
```

**AI Copilot:**
```
POST   /copilot/query               # Send query
GET    /copilot/history             # Conversation history
POST   /copilot/feedback            # Submit feedback
DELETE /copilot/session             # Clear session
```

**Admin:**
```
GET    /admin/users                 # List users
POST   /admin/users                 # Create user
PUT    /admin/users/:id             # Update user
DELETE /admin/users/:id             # Delete user
GET    /admin/audit-logs            # Audit logs
GET    /admin/api-keys              # API keys
POST   /admin/api-keys              # Generate API key
```

### 8.3 API Rate Limiting

```javascript
// Rate limiting configuration
const rateLimits = {
    anonymous: {
        windowMs: 15 * 60 * 1000, // 15 minutes
        max: 100 // 100 requests per window
    },
    authenticated: {
        windowMs: 15 * 60 * 1000,
        max: 1000
    },
    premium: {
        windowMs: 15 * 60 * 1000,
        max: 5000
    }
};

// Rate limiter middleware
const rateLimiter = rateLimit({
    windowMs: rateLimits.authenticated.windowMs,
    max: async (req) => {
        const tenant = await Tenant.findById(req.tenantId);
        return rateLimits[tenant.subscription_tier]?.max || 1000;
    },
    message: 'Too many requests, please try again later',
    standardHeaders: true,
    legacyHeaders: false
});
```

### 8.4 API Versioning

**Strategy:** URL-based versioning

```
/v1/bookings  → Current stable version
/v2/bookings  → New version with breaking changes
```

**Deprecation Policy:**
- Announce deprecation 6 months in advance
- Support old version for 12 months after new version release
- Provide migration guide and tools

---

## Scalability Design

### 9.1 Horizontal Scaling Strategy


**Application Layer:**
```
┌─────────────────────────────────────────────────────────────┐
│                    LOAD BALANCER                             │
│              (AWS ALB / NGINX / HAProxy)                     │
│  - Health checks                                             │
│  - SSL termination                                           │
│  - Request routing                                           │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────┬──────────┐
    │          │          │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐
│ API   │  │ API  │  │ API  │  │ API  │  │ API  │
│Server │  │Server│  │Server│  │Server│  │Server│
│  1    │  │  2   │  │  3   │  │  4   │  │  N   │
└───────┘  └──────┘  └──────┘  └──────┘  └──────┘

Auto-scaling based on:
- CPU utilization > 70%
- Memory utilization > 80%
- Request queue depth > 100
- Response time > 2s
```

**Database Layer:**
```
┌─────────────────────────────────────────────────────────────┐
│                  PRIMARY DATABASE                            │
│              (PostgreSQL Master)                             │
│  - Write operations                                          │
│  - Critical reads                                            │
└──────────────┬──────────────────────────────────────────────┘
               │
               │ Streaming Replication
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐
│Read   │  │Read  │  │Read  │  │Read  │
│Replica│  │Replica│ │Replica│ │Replica│
│  1    │  │  2   │  │  3   │  │  N   │
└───────┘  └──────┘  └──────┘  └──────┘

Read replicas for:
- Analytics queries
- Reporting
- Dashboard data
- ML feature extraction
```

**Caching Layer:**
```
┌─────────────────────────────────────────────────────────────┐
│                  REDIS CLUSTER                               │
│              (Master-Replica Setup)                          │
└─────────────────────────────────────────────────────────────┘

┌──────────┐  ┌──────────┐  ┌──────────┐
│ Master 1 │  │ Master 2 │  │ Master 3 │
│ (Shard 1)│  │ (Shard 2)│  │ (Shard 3)│
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
┌────▼─────┐  ┌───▼──────┐  ┌───▼──────┐
│ Replica  │  │ Replica  │  │ Replica  │
└──────────┘  └──────────┘  └──────────┘

Sharding strategy:
- Hash-based on tenant_id
- Consistent hashing for even distribution
```

### 9.2 Performance Optimization

**Database Query Optimization:**
```sql
-- Use EXPLAIN ANALYZE for query planning
EXPLAIN ANALYZE
SELECT * FROM bookings 
WHERE tenant_id = '...' 
  AND check_in_date >= '2026-03-01'
  AND check_in_date <= '2026-03-31';

-- Optimize with covering index
CREATE INDEX idx_bookings_covering 
ON bookings(tenant_id, check_in_date) 
INCLUDE (booking_reference, guest_name, status);

-- Use materialized views for complex aggregations
CREATE MATERIALIZED VIEW monthly_revenue_summary AS
SELECT 
    tenant_id,
    DATE_TRUNC('month', check_in_date) as month,
    COUNT(*) as total_bookings,
    SUM(total_amount) as total_revenue,
    AVG(room_rate) as avg_rate
FROM bookings
WHERE status = 'completed'
GROUP BY tenant_id, DATE_TRUNC('month', check_in_date);

-- Refresh materialized view daily
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue_summary;
```

**API Response Caching:**
```javascript
// Cache strategy
const cacheMiddleware = (ttl = 300) => {
    return async (req, res, next) => {
        const cacheKey = `${req.tenantId}:${req.path}:${JSON.stringify(req.query)}`;
        
        // Try to get from cache
        const cached = await redis.get(cacheKey);
        if (cached) {
            return res.json(JSON.parse(cached));
        }
        
        // Store original res.json
        const originalJson = res.json.bind(res);
        
        // Override res.json to cache response
        res.json = (data) => {
            redis.setex(cacheKey, ttl, JSON.stringify(data));
            return originalJson(data);
        };
        
        next();
    };
};

// Apply to routes
app.get('/api/v1/revenue/metrics', 
    tenantMiddleware,
    cacheMiddleware(300), // 5 minutes
    revenueController.getMetrics
);
```

**Database Connection Pooling:**
```javascript
// PostgreSQL connection pool
const pool = new Pool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    max: 20, // Maximum pool size
    min: 5,  // Minimum pool size
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000
});
```

### 9.3 Background Job Processing

**Job Queue Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    JOB PRODUCERS                             │
│  - API endpoints                                             │
│  - Scheduled tasks                                           │
│  - Webhooks                                                  │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                  MESSAGE QUEUE                               │
│              (Bull / Celery / RabbitMQ)                      │
│                                                              │
│  Queues:                                                     │
│  - high_priority (forecasting, pricing)                      │
│  - default (reports, notifications)                          │
│  - low_priority (data cleanup, archival)                     │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐
│Worker │  │Worker│  │Worker│  │Worker│
│  1    │  │  2   │  │  3   │  │  N   │
└───────┘  └──────┘  └──────┘  └──────┘

Auto-scaling workers based on queue depth
```

**Job Types:**
```javascript
// Data import job
queue.add('import-bookings', {
    tenantId: 'tenant-123',
    fileUrl: 's3://bucket/import.csv',
    userId: 'user-456'
}, {
    priority: 2,
    attempts: 3,
    backoff: {
        type: 'exponential',
        delay: 2000
    }
});

// Model training job
queue.add('train-forecast-model', {
    tenantId: 'tenant-123',
    modelType: 'prophet',
    dataRange: { start: '2024-01-01', end: '2026-02-01' }
}, {
    priority: 1,
    timeout: 3600000 // 1 hour
});

// Report generation job
queue.add('generate-report', {
    tenantId: 'tenant-123',
    reportType: 'monthly-revenue',
    period: '2026-02',
    recipients: ['manager@hotel.com']
}, {
    priority: 3,
    delay: 60000 // Delay 1 minute
});
```

---

## Security Architecture

### 10.1 Authentication & Authorization

**JWT Token Structure:**
```json
{
    "header": {
        "alg": "RS256",
        "typ": "JWT"
    },
    "payload": {
        "sub": "user-uuid",
        "email": "user@example.com",
        "role": "revenue_manager",
        "tenant_id": "tenant-uuid",
        "permissions": ["read:bookings", "write:pricing"],
        "iat": 1708000000,
        "exp": 1708003600
    }
}
```

**Token Management:**
```javascript
// Generate access token (15 minutes)
const accessToken = jwt.sign(
    { 
        sub: user.id,
        email: user.email,
        role: user.role,
        tenant_id: userTenant.tenant_id
    },
    privateKey,
    { 
        algorithm: 'RS256',
        expiresIn: '15m'
    }
);

// Generate refresh token (7 days)
const refreshToken = jwt.sign(
    { sub: user.id, type: 'refresh' },
    privateKey,
    { 
        algorithm: 'RS256',
        expiresIn: '7d'
    }
);

// Store refresh token hash in database
await db.query(
    'INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3)',
    [user.id, hashToken(refreshToken), new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)]
);
```

**Permission-Based Access Control:**
```javascript
const permissions = {
    'super_admin': ['*'],
    'property_admin': [
        'read:*', 'write:*', 'delete:bookings', 'manage:users'
    ],
    'revenue_manager': [
        'read:*', 'write:pricing', 'write:forecasts'
    ],
    'operations_manager': [
        'read:*', 'write:bookings'
    ],
    'analyst': [
        'read:*'
    ],
    'viewer': [
        'read:dashboard', 'read:reports'
    ]
};

// Permission check middleware
const requirePermission = (permission) => {
    return (req, res, next) => {
        const userPermissions = permissions[req.user.role];
        
        if (userPermissions.includes('*') || 
            userPermissions.includes(permission) ||
            userPermissions.some(p => p.endsWith(':*') && permission.startsWith(p.split(':')[0]))) {
            return next();
        }
        
        res.status(403).json({ error: 'Insufficient permissions' });
    };
};

// Apply to routes
app.delete('/api/v1/bookings/:id',
    authenticate,
    requirePermission('delete:bookings'),
    bookingController.delete
);
```

### 10.2 Data Encryption

**Encryption at Rest:**
```
- Database: PostgreSQL with transparent data encryption (TDE)
- File Storage: S3 with server-side encryption (SSE-S3 or SSE-KMS)
- Backups: Encrypted using AES-256
- Sensitive fields: Application-level encryption for PII
```

**Encryption in Transit:**
```
- TLS 1.3 for all API communications
- Certificate pinning for mobile apps (future)
- VPN for admin access to infrastructure
```

**Application-Level Encryption:**
```javascript
const crypto = require('crypto');

// Encrypt sensitive data
function encryptPII(data, key) {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    
    let encrypted = cipher.update(data, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    const authTag = cipher.getAuthTag();
    
    return {
        encrypted,
        iv: iv.toString('hex'),
        authTag: authTag.toString('hex')
    };
}

// Decrypt sensitive data
function decryptPII(encryptedData, key) {
    const decipher = crypto.createDecipheriv(
        'aes-256-gcm',
        key,
        Buffer.from(encryptedData.iv, 'hex')
    );
    
    decipher.setAuthTag(Buffer.from(encryptedData.authTag, 'hex'));
    
    let decrypted = decipher.update(encryptedData.encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    
    return decrypted;
}
```

### 10.3 Security Best Practices


**Input Validation:**
```javascript
const { body, param, query, validationResult } = require('express-validator');

// Validation middleware
const validateBooking = [
    body('guest_name').trim().isLength({ min: 2, max: 255 }),
    body('guest_email').isEmail().normalizeEmail(),
    body('check_in_date').isISO8601().toDate(),
    body('check_out_date').isISO8601().toDate()
        .custom((value, { req }) => {
            if (new Date(value) <= new Date(req.body.check_in_date)) {
                throw new Error('Check-out must be after check-in');
            }
            return true;
        }),
    body('num_guests').isInt({ min: 1, max: 10 }),
    body('room_rate').isFloat({ min: 0 }),
    
    (req, res, next) => {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        next();
    }
];

app.post('/api/v1/bookings', validateBooking, bookingController.create);
```

**SQL Injection Prevention:**
```javascript
// ALWAYS use parameterized queries
// BAD - Vulnerable to SQL injection
const query = `SELECT * FROM bookings WHERE id = '${req.params.id}'`;

// GOOD - Parameterized query
const query = 'SELECT * FROM bookings WHERE id = $1 AND tenant_id = $2';
const result = await db.query(query, [req.params.id, req.tenantId]);
```

**XSS Prevention:**
```javascript
// Sanitize user input
const sanitizeHtml = require('sanitize-html');

function sanitizeInput(input) {
    return sanitizeHtml(input, {
        allowedTags: [],
        allowedAttributes: {}
    });
}

// Apply to user-generated content
const sanitizedRequest = sanitizeInput(req.body.special_requests);
```

**CSRF Protection:**
```javascript
const csrf = require('csurf');

// CSRF protection middleware
const csrfProtection = csrf({ cookie: true });

// Apply to state-changing routes
app.post('/api/v1/bookings', csrfProtection, bookingController.create);
```

**Security Headers:**
```javascript
const helmet = require('helmet');

app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            scriptSrc: ["'self'"],
            imgSrc: ["'self'", "data:", "https:"],
        }
    },
    hsts: {
        maxAge: 31536000,
        includeSubDomains: true,
        preload: true
    }
}));
```

---

## Deployment Architecture

### 11.1 Cloud Infrastructure (AWS Example)

```
┌─────────────────────────────────────────────────────────────┐
│                      PRODUCTION ENVIRONMENT                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Route 53 (DNS)                                              │
│  - airbee.com → CloudFront                                   │
│  - api.airbee.com → ALB                                      │
└──────────────┬──────────────────────────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼────────────────────────────────────────┐
│ CloudFront   │  │  Application Load Balancer (ALB)          │
│ (CDN)        │  │  - SSL Termination                        │
│ - Static     │  │  - Health Checks                          │
│   Assets     │  │  - WAF Integration                        │
└──────────────┘  └──┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌──▼──────┐ ┌──▼──────────────────────────┐
│ ECS Fargate  │ │ ECS     │ │  Lambda Functions           │
│ (API)        │ │ (Workers)│ │  - Scheduled tasks          │
│ - Auto-scale │ │ - Jobs  │ │  - Event processing         │
│ - Multi-AZ   │ │         │ │                             │
└───────┬──────┘ └──┬──────┘ └─────────────────────────────┘
        │           │
        └─────┬─────┘
              │
    ┌─────────┼─────────┬─────────────┐
    │         │         │             │
┌───▼───┐ ┌──▼───┐ ┌──▼────┐ ┌──────▼──────┐
│ RDS   │ │ElastiCache│ S3  │ │  SageMaker  │
│Postgres│ │(Redis)│ │Storage│ │  (ML Models)│
│Multi-AZ│ │Cluster│ │       │ │             │
└───────┘ └──────┘ └───────┘ └─────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Monitoring & Logging                                        │
│  - CloudWatch (Metrics, Logs, Alarms)                        │
│  - X-Ray (Distributed Tracing)                               │
│  - GuardDuty (Threat Detection)                              │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 Container Configuration

**Dockerfile (Node.js API):**
```dockerfile
# Multi-stage build
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build TypeScript
RUN npm run build

# Production image
FROM node:18-alpine

WORKDIR /app

# Copy built artifacts
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

USER nodejs

EXPOSE 3000

CMD ["node", "dist/server.js"]
```

**Docker Compose (Development):**
```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:password@db:5432/airbee
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - ./api:/app
      - /app/node_modules

  ml-service:
    build: ./ml-service
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/airbee
    depends_on:
      - db

  db:
    image: timescale/timescaledb:latest-pg14
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=airbee
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
  redis_data:
```

### 11.3 CI/CD Pipeline

```yaml
# GitHub Actions workflow
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run linter
        run: npm run lint
      
      - name: Run tests
        run: npm test
      
      - name: Run security audit
        run: npm audit --audit-level=moderate

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: airbee-api
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster airbee-production \
            --service airbee-api \
            --force-new-deployment
```

### 11.4 Environment Configuration

**Environment Variables:**
```bash
# Application
NODE_ENV=production
PORT=3000
API_VERSION=v1

# Database
DATABASE_URL=postgresql://user:pass@host:5432/airbee
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=20

# Redis
REDIS_URL=redis://host:6379
REDIS_TTL=300

# JWT
JWT_SECRET=<secret-key>
JWT_EXPIRY=15m
REFRESH_TOKEN_EXPIRY=7d

# AWS
AWS_REGION=us-east-1
AWS_S3_BUCKET=airbee-storage
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>

# ML Services
ML_SERVICE_URL=http://ml-service:8000
OPENAI_API_KEY=<key>

# Monitoring
SENTRY_DSN=<dsn>
LOG_LEVEL=info
```

---

## Monitoring & Logging

### 12.1 Application Monitoring


**Metrics to Track:**

```javascript
// Application metrics
const metrics = {
    // Performance
    'api.request.duration': 'histogram',
    'api.request.count': 'counter',
    'api.error.count': 'counter',
    
    // Business metrics
    'bookings.created': 'counter',
    'forecasts.generated': 'counter',
    'pricing.recommendations': 'counter',
    'copilot.queries': 'counter',
    
    // System metrics
    'database.query.duration': 'histogram',
    'cache.hit.rate': 'gauge',
    'queue.depth': 'gauge',
    'ml.inference.duration': 'histogram',
    
    // User metrics
    'users.active': 'gauge',
    'tenants.active': 'gauge'
};

// Prometheus integration
const promClient = require('prom-client');

const httpRequestDuration = new promClient.Histogram({
    name: 'http_request_duration_seconds',
    help: 'Duration of HTTP requests in seconds',
    labelNames: ['method', 'route', 'status_code'],
    buckets: [0.1, 0.5, 1, 2, 5]
});

// Middleware to track metrics
app.use((req, res, next) => {
    const start = Date.now();
    
    res.on('finish', () => {
        const duration = (Date.now() - start) / 1000;
        httpRequestDuration
            .labels(req.method, req.route?.path || req.path, res.statusCode)
            .observe(duration);
    });
    
    next();
});

// Expose metrics endpoint
app.get('/metrics', async (req, res) => {
    res.set('Content-Type', promClient.register.contentType);
    res.end(await promClient.register.metrics());
});
```

**Health Check Endpoints:**
```javascript
// Liveness probe - is the app running?
app.get('/health/live', (req, res) => {
    res.status(200).json({ status: 'ok' });
});

// Readiness probe - is the app ready to serve traffic?
app.get('/health/ready', async (req, res) => {
    try {
        // Check database connection
        await db.query('SELECT 1');
        
        // Check Redis connection
        await redis.ping();
        
        res.status(200).json({
            status: 'ready',
            checks: {
                database: 'ok',
                cache: 'ok'
            }
        });
    } catch (error) {
        res.status(503).json({
            status: 'not ready',
            error: error.message
        });
    }
});

// Detailed health check
app.get('/health/detailed', async (req, res) => {
    const checks = {
        database: await checkDatabase(),
        cache: await checkRedis(),
        mlService: await checkMLService(),
        storage: await checkS3()
    };
    
    const allHealthy = Object.values(checks).every(c => c.status === 'ok');
    
    res.status(allHealthy ? 200 : 503).json({
        status: allHealthy ? 'healthy' : 'degraded',
        timestamp: new Date().toISOString(),
        checks
    });
});
```

### 12.2 Logging Strategy

**Structured Logging:**
```javascript
const winston = require('winston');

// Configure logger
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.errors({ stack: true }),
        winston.format.json()
    ),
    defaultMeta: {
        service: 'airbee-api',
        environment: process.env.NODE_ENV
    },
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ 
            filename: 'logs/error.log', 
            level: 'error' 
        }),
        new winston.transports.File({ 
            filename: 'logs/combined.log' 
        })
    ]
});

// Request logging middleware
app.use((req, res, next) => {
    const start = Date.now();
    
    res.on('finish', () => {
        logger.info('HTTP Request', {
            method: req.method,
            url: req.url,
            status: res.statusCode,
            duration: Date.now() - start,
            tenant_id: req.tenantId,
            user_id: req.user?.id,
            ip: req.ip,
            user_agent: req.get('user-agent')
        });
    });
    
    next();
});

// Error logging
app.use((err, req, res, next) => {
    logger.error('Application Error', {
        error: err.message,
        stack: err.stack,
        method: req.method,
        url: req.url,
        tenant_id: req.tenantId,
        user_id: req.user?.id
    });
    
    res.status(500).json({ error: 'Internal server error' });
});
```

**Log Levels:**
```
ERROR: Application errors, exceptions
WARN: Deprecated API usage, slow queries
INFO: HTTP requests, business events
DEBUG: Detailed debugging information
TRACE: Very detailed debugging (development only)
```

**Log Aggregation:**
```
- CloudWatch Logs (AWS)
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Datadog
- Splunk

Retention:
- ERROR logs: 90 days
- INFO logs: 30 days
- DEBUG logs: 7 days
```

### 12.3 Alerting Rules

**Critical Alerts (PagerDuty/Slack):**
```yaml
alerts:
  - name: High Error Rate
    condition: error_rate > 5%
    duration: 5m
    severity: critical
    
  - name: API Response Time
    condition: p95_latency > 2s
    duration: 5m
    severity: critical
    
  - name: Database Connection Pool Exhausted
    condition: db_pool_available < 2
    duration: 1m
    severity: critical
    
  - name: ML Model Accuracy Drop
    condition: forecast_mape > 20%
    duration: 1h
    severity: high
    
  - name: High Memory Usage
    condition: memory_usage > 90%
    duration: 5m
    severity: high
```

**Warning Alerts (Email/Slack):**
```yaml
alerts:
  - name: Increased Response Time
    condition: p95_latency > 1s
    duration: 10m
    severity: warning
    
  - name: Cache Hit Rate Low
    condition: cache_hit_rate < 70%
    duration: 15m
    severity: warning
    
  - name: Queue Depth High
    condition: queue_depth > 1000
    duration: 5m
    severity: warning
```

### 12.4 Distributed Tracing

**OpenTelemetry Integration:**
```javascript
const { NodeTracerProvider } = require('@opentelemetry/sdk-trace-node');
const { registerInstrumentations } = require('@opentelemetry/instrumentation');
const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');

// Initialize tracer
const provider = new NodeTracerProvider();
provider.register();

// Register instrumentations
registerInstrumentations({
    instrumentations: [
        new HttpInstrumentation(),
        new ExpressInstrumentation(),
    ],
});

// Custom span for business logic
const tracer = provider.getTracer('airbee-api');

async function generateForecast(tenantId, roomTypeId) {
    const span = tracer.startSpan('generate_forecast');
    span.setAttribute('tenant_id', tenantId);
    span.setAttribute('room_type_id', roomTypeId);
    
    try {
        // Business logic
        const data = await fetchHistoricalData(tenantId, roomTypeId);
        const forecast = await mlService.predict(data);
        
        span.setStatus({ code: SpanStatusCode.OK });
        return forecast;
    } catch (error) {
        span.setStatus({ 
            code: SpanStatusCode.ERROR, 
            message: error.message 
        });
        throw error;
    } finally {
        span.end();
    }
}
```

---

## Future Scalability Considerations

### 13.1 Microservices Evolution

**Current Monolithic API → Future Microservices:**

```
Phase 1 (Current): Modular Monolith
┌─────────────────────────────────────┐
│         Single API Service          │
│  ┌──────────┐  ┌──────────┐        │
│  │ Booking  │  │ Revenue  │        │
│  │ Module   │  │ Module   │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │Analytics │  │Customer  │        │
│  │ Module   │  │ Module   │        │
│  └──────────┘  └──────────┘        │
└─────────────────────────────────────┘

Phase 2 (Future): Microservices
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Booking  │  │ Revenue  │  │Analytics │
│ Service  │  │ Service  │  │ Service  │
└──────────┘  └──────────┘  └──────────┘
┌──────────┐  ┌──────────┐  ┌──────────┐
│Customer  │  │   ML     │  │Integration│
│ Service  │  │ Service  │  │  Service │
└──────────┘  └──────────┘  └──────────┘
```

**Migration Strategy:**
1. Identify service boundaries based on business domains
2. Extract one service at a time (strangler pattern)
3. Implement API gateway for routing
4. Use event-driven communication (Kafka, RabbitMQ)
5. Implement distributed transactions (Saga pattern)

### 13.2 Event-Driven Architecture

**Event Bus Implementation:**
```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT BUS (Kafka/RabbitMQ)                │
└─────────────────────────────────────────────────────────────┘

Events:
- booking.created
- booking.cancelled
- pricing.updated
- forecast.generated
- customer.segmented

┌──────────┐     ┌──────────┐     ┌──────────┐
│ Booking  │────▶│  Event   │────▶│ Revenue  │
│ Service  │     │   Bus    │     │ Service  │
└──────────┘     └────┬─────┘     └──────────┘
                      │
                      ├──────────▶┌──────────┐
                      │           │Analytics │
                      │           │ Service  │
                      │           └──────────┘
                      │
                      └──────────▶┌──────────┐
                                  │Notification│
                                  │ Service  │
                                  └──────────┘
```

### 13.3 Global Distribution

**Multi-Region Deployment:**
```
┌─────────────────────────────────────────────────────────────┐
│                    GLOBAL LOAD BALANCER                      │
│                  (Route 53 / CloudFlare)                     │
└──────────────┬──────────────────────────────────────────────┘
               │
        ┌──────┼──────┬──────────┐
        │      │      │          │
┌───────▼──┐ ┌▼──────▼┐ ┌───────▼──┐
│ US-EAST  │ │ EU-WEST │ │ AP-SOUTH │
│ (Primary)│ │(Secondary)│(Secondary)│
└──────────┘ └─────────┘ └──────────┘

Data Replication:
- Active-Active for read operations
- Active-Passive for write operations
- Cross-region database replication
- CDN for static assets
```

### 13.4 Advanced ML Capabilities

**Future ML Enhancements:**

1. **Real-Time Forecasting:**
   - Stream processing with Apache Flink
   - Online learning models
   - Sub-second predictions

2. **AutoML:**
   - Automated model selection
   - Hyperparameter optimization
   - Feature engineering automation

3. **Federated Learning:**
   - Train models across multiple properties
   - Preserve data privacy
   - Improve model accuracy

4. **Explainable AI:**
   - SHAP values for model interpretability
   - Feature importance visualization
   - Decision path explanation

### 13.5 Performance Targets (Next 2 Years)

```
Current → Target

API Response Time:
500ms (p95) → 200ms (p95)

Database Query Time:
100ms (p95) → 50ms (p95)

Forecast Accuracy:
85% → 90%

Concurrent Users:
500 → 5,000

Data Processing:
100K records/hour → 1M records/hour

ML Model Training:
1 hour → 15 minutes

System Uptime:
99.5% → 99.9%
```

---

## Appendix

### Technology Stack Summary

**Frontend:**
- React 18+
- TypeScript
- TailwindCSS
- React Query
- Chart.js/Recharts

**Backend:**
- Node.js/Express OR Django/DRF
- TypeScript/Python
- Bull/Celery (Job Queue)
- Socket.io (WebSocket)

**Database:**
- PostgreSQL 14+
- TimescaleDB (Time-series)
- Redis 7+ (Cache)

**AI/ML:**
- Python 3.11+
- FastAPI
- Scikit-learn
- Prophet
- TensorFlow/PyTorch
- LangChain
- MLflow

**Infrastructure:**
- Docker
- Kubernetes/ECS
- AWS/Azure/GCP
- CloudFront/CDN
- S3/Object Storage

**Monitoring:**
- Prometheus
- Grafana
- CloudWatch
- Sentry
- OpenTelemetry

### Key Design Decisions

1. **Multi-Tenant Architecture:** Shared database with tenant_id isolation for cost efficiency
2. **Modular Monolith:** Start with modular monolith, evolve to microservices as needed
3. **Time-Series Database:** TimescaleDB for efficient time-series data handling
4. **Caching Strategy:** Redis for session and query result caching
5. **ML Model Serving:** Separate Python service for ML operations
6. **API-First Design:** All functionality exposed through RESTful APIs
7. **Horizontal Scaling:** Stateless services for easy horizontal scaling
8. **Event-Driven:** Background jobs for long-running operations

---

## Document Control

- **Version:** 1.0
- **Date:** February 15, 2026
- **Status:** Production-Grade Design
- **Next Review:** May 15, 2026
- **Owner:** Engineering Team
- **Approvers:** CTO, Lead Architect, VP of Engineering

---

*This document is confidential and proprietary to AIR BEE. Unauthorized distribution is prohibited.*
