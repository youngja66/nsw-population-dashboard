import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pathlib

# --- Page Configuration ---
st.set_page_config(
    page_title="NSW Population Dashboard (Leaflet Map)",
    page_icon="🗺️",
    layout="wide",
)

# --- Define File Paths ---
# --- Define Relative File Paths ---
# Get the directory of the current script
APP_DIR = pathlib.Path(__file__).parent
# Define paths relative to the script's location
SHAPEFILE_PATH = APP_DIR / "data" / "lga.shp"
CSV_PATH = APP_DIR / "data" / "lga.csv"

# --- Data Loading Function (cached for performance) ---
@st.cache_data
def load_local_data(shp_path, csv_path):
    """
    Loads shapefile and CSV from local paths and re-projects the shapefile for web mapping.
    """
    if not shp_path.is_file():
        return None, None, f"Shapefile not found at: {shp_path}"
    if not csv_path.is_file():
        return None, None, f"CSV file not found at: {csv_path}"

    try:
        gdf = gpd.read_file(shp_path, engine='pyogrio').to_crs(epsg=4326)
    except Exception as e:
        return None, None, f"Fatal Error: Could not read or process shapefile. Details: {e}"

    try:
        pop_df = pd.read_csv(csv_path)
    except Exception as e:
        return None, None, f"Fatal Error: Could not read CSV file. Details: {e}"

    if "LGANAME" not in gdf.columns:
        return None, None, f"Shapefile missing 'LGANAME' column. Columns: {gdf.columns.to_list()}"
    if "LGANAME" not in pop_df.columns:
        return None, None, f"CSV missing 'LGANAME' column. Columns: {pop_df.columns.to_list()}"

    return gdf, pop_df, None

# --- Main Application Logic ---
st.title("NSW LGA Population Dashboard with Interactive Map")
st.write(f"Displaying data automatically loaded from `{SHAPEFILE_PATH}` and `{CSV_PATH}`.")

gdf, population_df, error_message = load_local_data(SHAPEFILE_PATH, CSV_PATH)

if error_message:
    st.error(error_message)
    st.stop()

merged_data = gdf.merge(population_df, on="LGANAME", how="left")
year_columns = sorted([col for col in population_df.columns if col.isnumeric()])

if not year_columns:
    st.error("No numeric year columns were found in the CSV file.")
    st.stop()

st.sidebar.header("Dashboard Controls")
selected_year = st.sidebar.selectbox(
    "Select a Year:",
    options=year_columns,
    index=len(year_columns) - 1,
)

st.header(f"Population Distribution for {selected_year}")
st.markdown("---")

map_data = merged_data.dropna(subset=[selected_year])

# Create the Folium (Leaflet) Map
m = folium.Map(location=[-32.5, 148.5], zoom_start=6, tiles="CartoDB positron")

if not map_data.empty:
    # #############################################################################
    # #############               FIX IS HERE               #############
    # #############################################################################
    # Create a new GeoDataFrame with ONLY the columns needed for the map.
    # This prevents non-serializable types (like Timestamp) from being passed to Folium.
    map_display_data = map_data[['geometry', 'LGANAME', selected_year]].copy()

    # Also, ensure the data column is a standard integer type
    map_display_data[selected_year] = map_display_data[selected_year].astype(int)
    # #############################################################################

    choropleth = folium.Choropleth(
        geo_data=map_display_data,  # Use the new, clean GeoDataFrame
        name='choropleth',
        data=map_display_data,      # Use the new, clean GeoDataFrame
        columns=['LGANAME', selected_year],
        key_on='feature.properties.LGANAME',
        fill_color='YlOrRd',
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f'Population in {selected_year}',
        highlight=True,
    ).add_to(m)

    folium.GeoJsonTooltip(
        fields=["LGANAME", selected_year],
        aliases=["LGA:", "Population:"],
        style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;"),
        sticky=True
    ).add_to(choropleth.geojson)

# Render the map
st_folium(m, use_container_width=True, height=600)

# --- Zonal Statistics (remains the same) ---
st.header(f"Zonal Statistics for {selected_year}")
st.markdown("---")
valid_data = merged_data.dropna(subset=[selected_year])

if not valid_data.empty:
    total_population = valid_data[selected_year].sum()
    median_population = valid_data[selected_year].median()
    lgas_with_data_count = len(valid_data)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Population", f"{int(total_population):,}")
    col2.metric("Median LGA Population", f"{int(median_population):,}")
    col3.metric("LGAs with Data", f"{lgas_with_data_count} / {len(gdf)}")

    st.markdown("---")
    col1_data, col2_data = st.columns(2)
    with col1_data:
        st.subheader("Top 5 LGAs by Population")
        st.dataframe(
            valid_data.nlargest(5, selected_year)[["LGANAME", selected_year]].rename(columns={selected_year: "Population"}).style.format({"Population": "{:,.0f}"}),
            use_container_width=True
        )
    with col2_data:
        st.subheader("Bottom 5 LGAs by Population")
        st.dataframe(
            valid_data.nsmallest(5, selected_year)[["LGANAME", selected_year]].rename(columns={selected_year: "Population"}).style.format({"Population": "{:,.0f}"}),
            use_container_width=True
        )
else:
    st.warning(f"No population data available for the selected year: {selected_year}")