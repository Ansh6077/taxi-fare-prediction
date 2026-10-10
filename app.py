import streamlit as st
import folium
from streamlit_folium import st_folium
from databricks.sdk import WorkspaceClient

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="NYC Taxi Fare Prediction",
    page_icon="🚕",
    layout="centered"
)

# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------

st.title("🚕 NYC Taxi Fare Prediction")

st.write(
    "Predict your taxi fare using a Machine Learning model."
)

st.divider()

# ---------------------------------------------------------
# NYC MAP
# ---------------------------------------------------------

st.subheader("🗺️ Select Your Trip Locations")

st.write(
    "Choose Pickup or Drop-off, then click on the map."
)

# Initialize pickup location
if "pickup_location" not in st.session_state:
    st.session_state.pickup_location = None

# Initialize drop-off location
if "dropoff_location" not in st.session_state:
    st.session_state.dropoff_location = None

# Select location type
location_type = st.radio(
    "What location do you want to select?",
    ["📍 Pickup", "🚩 Drop-off"],
    horizontal=True
)

# Create NYC map
m = folium.Map(
    location=[40.7580, -73.9855],
    zoom_start=11
)

# ---------------------------------------------------------
# PICKUP MARKER
# ---------------------------------------------------------

if st.session_state.pickup_location:

    folium.Marker(
        [
            st.session_state.pickup_location["lat"],
            st.session_state.pickup_location["lng"]
        ],
        popup="📍 Pickup Location",
        tooltip="Pickup",
        icon=folium.Icon(
            color="green",
            icon="play"
        )
    ).add_to(m)

# ---------------------------------------------------------
# DROP-OFF MARKER
# ---------------------------------------------------------

if st.session_state.dropoff_location:

    folium.Marker(
        [
            st.session_state.dropoff_location["lat"],
            st.session_state.dropoff_location["lng"]
        ],
        popup="🚩 Drop-off Location",
        tooltip="Drop-off",
        icon=folium.Icon(
            color="red",
            icon="flag"
        )
    ).add_to(m)

# ---------------------------------------------------------
# DISPLAY MAP
# ---------------------------------------------------------

map_data = st_folium(
    m,
    width=700,
    height=450,
    returned_objects=["last_clicked"]
)

# ---------------------------------------------------------
# HANDLE MAP CLICK
# ---------------------------------------------------------

if map_data and map_data.get("last_clicked"):

    clicked = map_data["last_clicked"]

    selected_location = {
        "lat": clicked["lat"],
        "lng": clicked["lng"]
    }

    if location_type == "📍 Pickup":

        st.session_state.pickup_location = selected_location

    else:

        st.session_state.dropoff_location = selected_location

    st.rerun()

# ---------------------------------------------------------
# DISPLAY SELECTED LOCATIONS
# ---------------------------------------------------------

if st.session_state.pickup_location:

    st.success(
        f"📍 Pickup: "
        f"{st.session_state.pickup_location['lat']:.5f}, "
        f"{st.session_state.pickup_location['lng']:.5f}"
    )

if st.session_state.dropoff_location:

    st.success(
        f"🚩 Drop-off: "
        f"{st.session_state.dropoff_location['lat']:.5f}, "
        f"{st.session_state.dropoff_location['lng']:.5f}"
    )

st.divider()

# ---------------------------------------------------------
# TRIP DETAILS
# ---------------------------------------------------------

st.subheader("Enter Trip Details")

col1, col2 = st.columns(2)

# ---------------------------------------------------------
# LEFT COLUMN
# ---------------------------------------------------------

with col1:

    trip_distance = st.number_input(
        "Trip Distance (miles)",
        min_value=0.1,
        value=2.5,
        step=0.1
    )

    passenger_count = st.number_input(
        "Passenger Count",
        min_value=1,
        max_value=6,
        value=2,
        step=1
    )

    trip_duration = st.number_input(
        "Trip Duration (minutes)",
        min_value=1.0,
        value=20.0,
        step=1.0
    )

    pickup_hour = st.number_input(
        "Pickup Hour (0–23)",
        min_value=0,
        max_value=23,
        value=18,
        step=1
    )

# ---------------------------------------------------------
# RIGHT COLUMN
# ---------------------------------------------------------

with col2:

    pickup_month = st.number_input(
        "Pickup Month (1–4)",
        min_value=1,
        max_value=4,
        value=3,
        step=1
    )

    pickup_day_of_week = st.number_input(
        "Pickup Day of Week (0–6)",
        min_value=0,
        max_value=6,
        value=2,
        step=1
    )

    pu_location = st.number_input(
        "Pickup Location ID",
        min_value=1,
        value=161,
        step=1
    )

    do_location = st.number_input(
        "Drop-off Location ID",
        min_value=1,
        value=236,
        step=1
    )

st.divider()

# ---------------------------------------------------------
# PREDICT FARE
# ---------------------------------------------------------

if st.button(
    "🔮 Predict Fare",
    use_container_width=True
):

    try:

        with st.spinner(
            "Predicting your taxi fare..."
        ):

            # Connect to Databricks
            workspace = WorkspaceClient(
                host=st.secrets["DATABRICKS_HOST"],
                client_id=st.secrets["DATABRICKS_CLIENT_ID"],
                client_secret=st.secrets["DATABRICKS_CLIENT_SECRET"]
            )

            # Send data to model serving endpoint
            response = workspace.serving_endpoints.query(
                name="taxi-fare-prediction-endpoint",
                dataframe_records=[
                    {
                        "trip_distance": trip_distance,
                        "passenger_count": passenger_count,
                        "pickup_hour": pickup_hour,
                        "pickup_month": pickup_month,
                        "pickup_day_of_week": pickup_day_of_week,
                        "trip_duration_minutes": trip_duration,
                        "PULocationID": pu_location,
                        "DOLocationID": do_location
                    }
                ]
            )

            # Get prediction
            prediction = response.predictions[0]

        # Display prediction
        st.success(
            f"💰 Predicted Taxi Fare: ${prediction:.2f}"
        )

        st.caption(
            "Prediction generated by a deployed Random Forest model."
        )

    except Exception as e:

        st.error(
            f"Prediction failed: {type(e).__name__}: {e}"
        )
