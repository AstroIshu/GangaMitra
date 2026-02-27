# 📁 Project Structure

This document describes the organized folder structure of the GangaMitra project.

## Directory Layout

```
GangaMitra/
├── src/                          # Source code
│   ├── core/                     # Core simulation components
│   │   ├── generator.py          # Terrain data generator (ZeroMQ publisher)
│   │   ├── subscriber.py         # Data subscriber utility
│   │   └── visualizer.py         # Real-time visualization
│   ├── simulators/               # Physics simulators
│   │   ├── pybullet_terrain.py   # Main PyBullet terrain simulator
│   │   └── simulation_with_robot.py  # Simulator with robot integration
│   ├── robots/                   # Robot implementations
│   │   ├── simple_robot.py       # Simple robot controller
│   │   └── pybullet_hexapod.py   # Hexapod robot
│   ├── pipeline/                 # Data processing pipeline
│   │   └── pathway_pipeline.py   # Pathway stream processing pipeline
│   └── ui/                       # User interfaces
│       ├── app.py                # Streamlit web application
│       └── dashboard.py          # Performance monitoring dashboard
├── docker/                       # Docker configuration
│   ├── docker-compose.yml        # Docker Compose orchestration
│   └── Dockerfile.pathway        # Pathway service container
├── requirements/                 # Python dependencies
│   ├── requirements.txt          # Main requirements
│   ├── requirements_pathway.txt  # Pathway-specific requirements
│   └── requirement_app.txt       # Streamlit app requirements
├── experiments/                  # Experimental code and tests
│   ├── test_*.py                 # Various physics engine tests
│   ├── *.xml                     # MuJoCo model files
│   └── working_world_model.py    # Working prototypes
├── logs/                         # Log files
│   ├── err.txt                   # General error logs
│   ├── sim_err.txt               # Simulation error logs
│   ├── sim_out.txt               # Simulation output logs
│   └── misc.txt                  # Miscellaneous logs
├── run_generator.py              # Helper script to run generator
├── run_pipeline.py               # Helper script to run pipeline
├── run_simulator.py              # Helper script to run simulator
├── run_dashboard.py              # Helper script to run dashboard
├── run_app.py                    # Helper script to run Streamlit app
└── README.md                     # Project documentation
```

## Component Organization

### Core (`src/core/`)
Contains the fundamental data generation and visualization components:
- **generator.py**: Publishes terrain data via ZeroMQ
- **subscriber.py**: Generic subscriber for testing
- **visualizer.py**: Real-time terrain visualization

### Simulators (`src/simulators/`)
Physics simulation engines using PyBullet:
- **pybullet_terrain.py**: Main terrain simulator with enhanced features
- **simulation_with_robot.py**: Integrated robot and terrain simulation

### Robots (`src/robots/`)
Robot controller implementations:
- **simple_robot.py**: Basic robot with movement and navigation
- **pybullet_hexapod.py**: Advanced hexapod robot model

### Pipeline (`src/pipeline/`)
Real-time data processing:
- **pathway_pipeline.py**: Pathway-based stream processing for traversability analysis

### UI (`src/ui/`)
User interfaces and dashboards:
- **app.py**: Streamlit web application for control and monitoring
- **dashboard.py**: Matplotlib-based performance dashboard

### Docker (`docker/`)
Containerization configuration:
- **docker-compose.yml**: Service orchestration
- **Dockerfile.pathway**: Pathway service container definition

### Requirements (`requirements/`)
Python package dependencies organized by component

### Experiments (`experiments/`)
Prototype code and experimental features (formerly "useless trials")

### Logs (`logs/`)
Application and simulation logs

## Running Components

You can run components directly from the project root using the helper scripts:

```bash
# Run the terrain generator
python run_generator.py

# Run the Pathway pipeline
python run_pipeline.py

# Run the PyBullet simulator
python run_simulator.py

# Run the performance dashboard
python run_dashboard.py

# Run the Streamlit app
python run_app.py
# Or directly: streamlit run src/ui/app.py
```

## Docker Deployment

Run the Pathway pipeline in Docker:

```bash
cd docker
docker-compose up
```

The Docker Compose context is set to the parent directory, so all source files are accessible during build.

## Import Structure

All modules in `src/` are organized as proper Python packages with `__init__.py` files. The helper scripts automatically add `src/` to the Python path, so you can run them from the project root without issues.

## Benefits of This Structure

1. **Clear Separation of Concerns**: Each directory has a specific purpose
2. **Scalability**: Easy to add new components without cluttering
3. **Professional**: Follows Python project best practices
4. **Maintainability**: Easy to locate and update specific functionality
5. **Docker-Ready**: Structure supports containerization
6. **Clean Root**: Root directory only contains documentation and helper scripts
