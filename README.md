CAIRO © ~ Compile AERMOD Input and Risk Omniware ©

Created by MSc Dominik Subotić in collaboration with Prof. Giorgio Passerini and PhD Simone Virgili at Universita Politecnica delle Marche, Italy, in 2025.
CAIRO © for AERMOD is a QGIS plugin developed to create and run AERMAP, AERMOD, and AERPLOT input files and run forward, backward and population risk analysis, with integrated map input, domain and source visualization, and automated project folder structure. Its aimed at streamlining the process of creating complex input files with unique syntax and running them, eliminating the need to manually write inputs and execute the program through Windows Shell.
Order of operations:
1. AERMAP Input Generator
2. AERMAP
3. AERMOD Input Generator
4. AERMOD
5. AERPLOT Input Generator
6. AERPLOT
7. Risk Assessment
8. Quantitative Population Risk Assessment

**AERMAP** is a terrain preprocessor. **AERMOD** is a steady-state plume dispersion modeling software. **AERPLOT** is a postprocessor for visualizing AERMOD results, developed by EPA.
Risk assessment is performed by applying backward and forward risk models to AERPLOT output, with tabular and map output, based on the Consolidated Table of OEHHA/ARB Approved Risk Assessment Health Values.

#### AERMAP features: 
 - Rectangular, Polar and Discrete receptor grid 
 - Map input of Anchor/Center/Receptor
 - Live Domain visualization
 - Automatic file fetching, copying and project folder structure

#### AERMOD features: 
- Urban areas and sources
- Point, Line, AreaPolygon and Volume sources
 - `ALL` keyword for group sources to include all sources
 - `ALLRURAL` keyword for group sources to include all normal (non-urban) sources
 - `ALLURBAN` keyword for group sources to include all urban sources
 - Map input and live visualization of sources, along with attribute table including source metadata
 - Rectable, Maxtable, Rankfile, Maxifile, Plotfile outputs
 - Automatic file fetching, copying and project folder structure

#### AEPLOT features: 
- Instantaneous Multiple plot input file creation and processing
 - Creates subfolder for every plotfile (Input file generator) and runs all kmz
 conversions at once (AERPLOT)

### Risk assessment features:
 - Backward and forward model
 - Population Risk Assessment based on GEOSTAT data and region averaged AERMOD output
 - Acute non-cancer risk (ACUTE) and chronic cancer (R) and non-cancer risk (HI)
 - Outdoor and Indoor vapor inhalation risk
 - Most Critical Receptor
 - Editable specific exposure parameters table
 - Leverages AERPLOT for risk map creation and relies on the created folder structure
 - Requires running AERPLOT postprocessing on 1h (for acute risk) and ANNUAL or PERIOD (for R and HI) averaging periods using CAIRO, due to the specific project folder structure Quantitative Population Risk Assessment averages the risk and concentration over the user selected area level and outputs a list of areas, their population, average concentration and risk. It automatically bridges discrepancies in .shp file and .plt file CRS.

#### Risk assessment formulation:

Chronic cancer risk: $R = C * IUR * EC$

Chronic non-cancer risk: $HI = C * (EC/RfC)$

Acute non-cancer risk: $ACUTE = C * (EC/aRfC)$

Where:
- `C` - AERPLOT per receptor Concentration at point of exposure
- `IUR` - Inhalation unit risk [µg/m3] [ $\mu g$ / $m^{3}$] [ $\dfrac{\mu g}{m^3}$ ] <!-- Not sure which looks better -->
- `RfC` - Chronic reference concentration [ $\mu g$ / $m^{3}$] <!-- or [µg/m3] or [ $\dfrac{\mu g}{m^3}$ ] -->
- `aRfC` - Acute reference concentration [ $\mu g$ / $m^{3}$] <!-- or [µg/m3] or [ $\dfrac{\mu g}{m^3}$ ] -->
- `EC` - Specific Exposure
$EC = (CR * Efg * EF * ED)/(BW * AT * 365)$
  - Where:
    - `CR` - Contact rate [ $m^3/h$]
      - for Outdoor inhalation CR=Bo(Outdoor vapor inhalation rate)
      - for Indoor inhalation CR=Bi(Indoor vapor inhalation rate)
    - `Efg` - Daily frequency; `Efgo` (outdoor); `Efgi` (indoor) [ $h/d$]
    - `EF` - Exposure frequency [ $days/year$]
    - `ED` - Exposure duration [ $years$]
    - `BW` - Body weight [ $kg$]
    - `AT` - Averaging time (for carcinogens), for non-carcinogens AT=ED [ $years$]

