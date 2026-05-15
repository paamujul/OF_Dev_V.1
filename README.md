

## Project Structure

- `algorithms/` - Core analytic models (Biomechanics, Bloodwork, Travel).
- `config/` - Project-wide settings and constants.
- `data/` - Datasets and generation scripts.
  - `generators/` - Scripts to synthesize simulated data.
  - `mock/` - Example JSON payloads.
- `data_struct/` - Data structure definitions and profile models.
- `main.py` - The main entry point to run the integrated algorithms.

## Generating Data

To generate mock simulation data (such as biomechanics telemetry or EMG session data):

1. Open your terminal.
2. Run any of the generator scripts using Python. For example:
   ```bash
   python data/generators/javelin_telemetry.py
   python data/generators/emg_generator.py
   python data/generators/muscle_arch_generator.py
   ```
3. The generated data will automatically be saved into the `data/mock/` folder as `.json` files, ready to be used by the analytics pipeline.
