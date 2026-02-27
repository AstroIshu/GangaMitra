# 🔄 Migration Guide: New Project Structure

This guide helps you understand the changes made to the GangaMitra project structure and how to adapt your workflow.

## What Changed?

The project has been reorganized from a flat structure to a professional, hierarchical structure.

### Before (Flat Structure)
```
GangaMitra/
├── app.py
├── dashboard.py
├── generator.py
├── pathway_pipeline.py
├── pybullet_terrain.py
├── simple_robot.py
├── ... (all files in root)
```

### After (Organized Structure)
```
GangaMitra/
├── src/
│   ├── core/          # Core components
│   ├── simulators/    # Physics simulators
│   ├── robots/        # Robot implementations
│   ├── pipeline/      # Data processing
│   └── ui/            # User interfaces
├── docker/            # Docker configuration 
├── requirements/      # Dependencies
├── experiments/       # Test/experimental code
├── logs/              # Log files
└── run_*.py          # Helper scripts
```

## File Relocations

| Old Location | New Location |
|-------------|-------------|
| `generator.py` | `src/core/generator.py` |
| `subscriber.py` | `src/core/subscriber.py` |
| `visualizer.py` | `src/core/visualizer.py` |
| `pybullet_terrain.py` | `src/simulators/pybullet_terrain.py` |
| `simulation_with_robot.py` | `src/simulators/simulation_with_robot.py` |
| `simple_robot.py` | `src/robots/simple_robot.py` |
| `pybullet_hexapod.py` | `src/robots/pybullet_hexapod.py` |
| `pathway_pipeline.py` | `src/pipeline/pathway_pipeline.py` |
| `app.py` | `src/ui/app.py` |
| `dashboard.py` | `src/ui/dashboard.py` |
| `docker-compose.yml` | `docker/docker-compose.yml` |
| `Dockerfile.pathway` | `docker/Dockerfile.pathway` |
| `requirements*.txt` | `requirements/requirements*.txt` |
| `useless trials/` | `experiments/` |
| `*.txt` logs | `logs/*.txt` |

## Running Commands

### Before
```bash
python generator.py
python pathway_pipeline.py
python pybullet_terrain.py
python dashboard.py
streamlit run app.py
```

### After (Recommended)
```bash
python run_generator.py
python run_pipeline.py
python run_simulator.py
python run_dashboard.py
python run_app.py
```

### Alternative (Direct Execution)
```bash
python src/core/generator.py
python src/pipeline/pathway_pipeline.py
python src/simulators/pybullet_terrain.py
python src/ui/dashboard.py
streamlit run src/ui/app.py
```

## Import Changes

### If you have custom scripts that import project modules:

**Before:**
```python
from simple_robot import SimpleRobot
from pybullet_terrain import EnhancedTerrain
```

**After:**
```python
import sys
import os
sys.path.insert(0, 'src')

from src.robots.simple_robot import SimpleRobot
from src.simulators.pybullet_terrain import EnhancedTerrain
```

**Or use the helper scripts as examples** - they handle path setup automatically.

## Docker Changes

### Before
```bash
docker-compose up
```

### After
```bash
cd docker
docker-compose up
```

The Docker Compose file now uses the parent directory as build context, so it can access all source files.

## Installing Dependencies

### Before
```bash
pip install -r requirements.txt
pip install -r requirements_pathway.txt
pip install -r requirement_app.txt
```

### After
```bash
pip install -r requirements/requirements.txt
pip install -r requirements/requirements_pathway.txt
pip install -r requirements/requirement_app.txt
```

## Benefits of New Structure

1. **Clear Organization**: Easy to find related components
2. **Scalability**: Can add more modules without cluttering
3. **Professional**: Follows Python best practices
4. **Maintainability**: Easier to understand and modify
5. **Clean Root**: Only documentation and helper scripts at root
6. **Better Git Management**: `.gitignore` now properly structured

## Troubleshooting

### Import Errors
If you get `ModuleNotFoundError`, ensure you're either:
1. Using the `run_*.py` helper scripts from the root directory, OR
2. Adding `src` to your Python path:
   ```python
   import sys
   sys.path.insert(0, 'src')
   ```

### Docker Build Fails
Make sure you're running `docker-compose` from inside the `docker/` directory, or specify the config file:
```bash
docker-compose -f docker/docker-compose.yml up
```

### Can't Find Files
All files are in their respective directories. Use the table above or check [STRUCTURE.md](STRUCTURE.md) for the complete layout.

## Backward Compatibility

The helper scripts (`run_*.py`) ensure backward compatibility. They:
- Set up Python paths correctly
- Can be run from the project root
- Work exactly like the old flat structure

## Need Help?

- See [STRUCTURE.md](STRUCTURE.md) for complete directory structure
- See [README.md](README.md) for usage instructions
- Check the helper scripts (`run_*.py`) for examples of proper path setup

---

**Note**: This reorganization does not change functionality - only file locations. All features work exactly as before.
