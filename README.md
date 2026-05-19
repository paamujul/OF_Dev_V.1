

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

## Running the AI Advisors & Simulating Results

To recreate the same AI-driven advisory results and simulate the multi-day scenarios on your local machine:

1. **Generate the Base Data**: First, ensure you have generated the mock data using the steps in the **Generating Data** section above.
2. **Run the Multi-Day Advisory**: 
   This script simulates an athlete's progress over multiple days and generates dynamic AI insights based on their trajectory.
   ```bash
   python ai/run_multiday_advisory.py
   ```
3. **Run the Research Advisor**: 
   This script leverages advanced AI to provide research-backed recommendations and protocol adjustments.
   ```bash
   python ai/run_research_advisor.py
   ```
4. **View the Output**: The AI-generated results and insights will be printed to your terminal and saved as JSON files in the `outputs/` directory, mirroring the exact insights generated on our end.

*Note: Ensure you have your `GEMINI_API_KEY` (or the relevant API key) exported as an environment variable before running the AI scripts.*
