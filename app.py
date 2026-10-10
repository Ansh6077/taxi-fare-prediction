import os

import folium
import requests
import streamlit as st
from databricks.sdk import WorkspaceClient
from shapely.geometry import Point, shape
from streamlit_folium import st_folium


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="NYC Taxi Fare Predictor",
    page_icon="🚕",
    layout="wide"
)

st.title("🚕 NYC Taxi Fare Predictor")
st.write(
    "Select your pickup and drop-off locations on the map "
    "to estimate your taxi fare."
)


# --------------------------------------------------
# DATBRICKS CONNECTION
# --------------------------------------------------

def get_workspace_client():
    """Create an authenticated Databricks workspace client."""

    os.environ["DATABRICKS_HOST"] = st.secrets["DATABRICKS_HOST"]
    os.environ["DATABRICKS_CLIENT_ID"] = st.secrets[
        "DATABRICKS_CLIENT_ID"
    ]
    os.environ["DATABRICKS_CLIENT_SECRET"] = st.secrets[
        "DATABRICKS_CLIENT_SECRET"
    ]

    return WorkspaceClient()


# --------------------------------------------------
# LOAD NYC TAXI ZONES
# --------------------------------------------------

@st.cache_data(ttl=86400)
def load_taxi_zones():
    """Download and cache the official NYC taxi zone polygons."""

    url = (
        "https://data.cityofnewyork.us/api/v3/views/"
        "8meu-9t5y/query.geojson?accessType=DOWNLOAD"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    geojson = response.json()

    zones = []

    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})

        # Handle differences in property-name capitalization.
        normalized = {
            str(key).lower(): value
            for key, value in properties.items()
        }

        geometry_data = feature.get("geometry")

        if not geometry_data:
            continue

        location_id = (
            normalized.get("locationid")
            or normalized.get("location_id")
        )

        zone_name = normalized.get("zone", "Unknown Zone")
        borough = normalized.get("borough", "Unknown Borough")

        if location_id is None:
            continue

        zones.append(
            {
                "location_id": int(float(location_id)),
                "zone": zone_name,
                "borough": borough,
                "geometry": shape(geometry_data),
            }
        )

    if not zones:
        raise ValueError(
            "No taxi zones were found in the downloaded dataset."
        )

    return zones


# --------------------------------------------------
# FIND ZONE FROM MAP COORDINATES
# --------------------------------------------------

def find_taxi_zone(latitude, longitude, zones):
    """Find the taxi zone containing a clicked map location."""

    clicked_point = Point(longitude, latitude)

    for zone in zones:
        if zone["geometry"].covers(clicked_point):
            return {
                "lat": latitude,
                "lng": longitude,
                "location_id": zone["location_id"],
                "zone": zone["zone"],
                "borough": zone["borough"],
            }

    return None


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "pickup_location" not in st.session_state:
    st.session_state.pickup_location = None

if "dropoff_location" not in st.session_state:
    st.session_state.dropoff_location = None

if "last_processed_click" not in st.session_state:
    st.session_state.last_processed_click = None


# --------------------------------------------------
# LOAD ZONE DATA
# --------------------------------------------------

try:
    taxi_zones = load_taxi_zones()
except Exception:
    st.error(
        "Unable to load NYC taxi zone information. "
        "Please refresh the page and try again."
    )
    st.stop()


# --------------------------------------------------
# MAP LOCATION SELECTION
# --------------------------------------------------

st.subheader("📍 Select Your Locations")

location_type = st.radio(
    "What location do you want to select?",
    ["📍 Pickup", "🚩 Drop-off"],
    horizontal=True,
)

st.info(
    "Choose Pickup or Drop-off above, then click the "
    "corresponding location on the map."
)

taxi_map = folium.Map(
    location=[40.7580, -73.9855],
    zoom_start=11,
    control_scale=True,
)

# Show the selected pickup marker.
pickup = st.session_state.pickup_location

if pickup:
    folium.Marker(
        location=[pickup["lat"], pickup["lng"]],
        tooltip=f"Pickup: {pickup['zone']}",
        popup=(
            f"Pickup Zone: {pickup['zone']}<br>"
            f"Borough: {pickup['borough']}<br>"
            f"Location ID: {pickup['location_id']}"
        ),
        icon=folium.Icon(color="green", icon="ok-sign"),
    ).add_to(taxi_map)

# Show the selected drop-off marker.
dropoff = st.session_state.dropoff_location

if dropoff:
    folium.Marker(
        location=[dropoff["lat"], dropoff["lng"]],
        tooltip=f"Drop-off: {dropoff['zone']}",
        popup=(
            f"Drop-off Zone: {dropoff['zone']}<br>"
            f"Borough: {dropoff['borough']}<br>"
            f"Location ID: {dropoff['location_id']}"
        ),
        icon=folium.Icon(color="red", icon="flag"),
    ).add_to(taxi_map)

map_data = st_folium(
    taxi_map,
    width=900,
    height=500,
    returned_objects=["last_clicked"],
    key="nyc_taxi_map",
)

# Process each new map click only once.
clicked = map_data.get("last_clicked") if map_data else None

if clicked:
    latitude = clicked.get("lat")
    longitude = clicked.get("lng")

    if latitude is not None and longitude is not None:
        click_key = (
            round(latitude, 6),
            round(longitude, 6),
        )

        if click_key != st.session_state.last_processed_click:
            st.session_state.last_processed_click = click_key

            selected_zone = find_taxi_zone(
                latitude,
                longitude,
                taxi_zones,
            )

            if selected_zone:
                if location_type == "📍 Pickup":
                    st.session_state.pickup_location = selected_zone
                else:
                    st.session_state.dropoff_location = selected_zone

                st.rerun()

            else:
                st.warning(
                    "That point is outside a recognized taxi zone. "
                    "Please click on land within New York City."
                )


# --------------------------------------------------
# DISPLAY SELECTED ZONES
# --------------------------------------------------

st.subheader("🗺️ Selected Taxi Zones")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📍 Pickup")

    pickup = st.session_state.pickup_location

    if pickup:
        st.success(
            f"Zone: {pickup['zone']}\n\n"
            f"Borough: {pickup['borough']}\n\n"
            f"Location ID: {pickup['location_id']}"
        )
    else:
        st.warning("Select your pickup location on the map.")

with col2:
    st.markdown("### 🚩 Drop-off")

    dropoff = st.session_state.dropoff_location

    if dropoff:
        st.success(
            f"Zone: {dropoff['zone']}\n\n"
            f"Borough: {dropoff['borough']}\n\n"
            f"Location ID: {dropoff['location_id']}"
        )
    else:
        st.warning("Select your drop-off location on the map.")


# --------------------------------------------------
# TRIP DETAILS
# --------------------------------------------------

st.divider()
st.subheader("🚖 Trip Details")

col1, col2, col3 = st.columns(3)

with col1:
    trip_distance = st.number_input(
        "Trip Distance (miles)",
        min_value=0.1,
        max_value=100.0,
        value=2.5,
        step=0.1,
    )

    passenger_count = st.number_input(
        "Passenger Count",
        min_value=1,
        max_value=6,
        value=2,
        step=1,
    )

    trip_duration = st.number_input(
        "Trip Duration (minutes)",
        min_value=1.0,
        max_value=300.0,
        value=20.0,
        step=1.0,
    )

with col2:
    pickup_hour = st.selectbox(
        "Pickup Hour",
        options=list(range(24)),
        index=18,
    )

    pickup_month = st.selectbox(
        "Pickup Month",
        options=list(range(1, 13)),
        index=2,
    )

with col3:
    pickup_day_of_week = st.selectbox(
        "Pickup Day of Week",
        options=list(range(7)),
        index=2,
        format_func=lambda day: [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ][day],
    )

    st.write("**Pickup Location ID**")

    if pickup:
        st.text_input(
            "Pickup Zone ID",
            value=str(pickup["location_id"]),
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.text_input(
            "Pickup Zone ID",
            value="Select on map",
            disabled=True,
            label_visibility="collapsed",
        )

    st.write("**Drop-off Location ID**")

    if dropoff:
        st.text_input(
            "Drop-off Zone ID",
            value=str(dropoff["location_id"]),
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.text_input(
            "Drop-off Zone ID",
            value="Select on map",
            disabled=True,
            label_visibility="collapsed",
        )


# --------------------------------------------------
# PREDICT FARE
# --------------------------------------------------

if st.button("💰 Predict Taxi Fare", type="primary"):

    pickup = st.session_state.pickup_location
    dropoff = st.session_state.dropoff_location

    if not pickup or not dropoff:
        st.warning(
            "Please select both pickup and drop-off zones "
            "on the map before predicting the fare."
        )

    elif trip_distance <= 0 or trip_duration <= 0:
        st.warning("Trip distance and duration must be greater than zero.")

    else:
        with st.spinner("Predicting your taxi fare..."):

            try:
                workspace = get_workspace_client()

                response = workspace.serving_endpoints.query(
                    name="taxi-fare-prediction-endpoint",
                    dataframe_records=[
                        {
                            "trip_distance": float(trip_distance),
                            "passenger_count": int(passenger_count),
                            "pickup_hour": int(pickup_hour),
                            "pickup_month": int(pickup_month),
                            "pickup_day_of_week": int(
                                pickup_day_of_week
                            ),
                            "trip_duration_minutes": float(
                                trip_duration
                            ),
                            "PULocationID": int(
                                pickup["location_id"]
                            ),
                            "DOLocationID": int(
                                dropoff["location_id"]
                            ),
                        }
                    ],
                )

                prediction = response.predictions[0]

                st.success("Fare prediction completed!")

                st.metric(
                    label="Estimated Taxi Fare",
                    value=f"${float(prediction):,.2f}",
                )

                st.caption(
                    f"Pickup: {pickup['zone']}, "
                    f"{pickup['borough']} "
                    f"(ID: {pickup['location_id']})"
                )

                st.caption(
                    f"Drop-off: {dropoff['zone']}, "
                    f"{dropoff['borough']} "
                    f"(ID: {dropoff['location_id']})"
                )

                st.caption(
                    "This is a machine-learning estimate, "
                    "not an official taxi fare quote."
                )

            except Exception:
                st.error(
                    "Fare prediction failed. Please try again later."
                )
