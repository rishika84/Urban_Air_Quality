import panel as pn
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from datetime import datetime, timedelta

# Configure Panel with memory optimizations
pn.extension('plotly', sizing_mode='stretch_width')
pn.config.cache = False  # Disable caching to save memory on free tier

# Environment configuration for deployment
PORT = int(os.environ.get('PORT', 5006))
ALLOW_WEBSOCKET_ORIGIN = os.environ.get('PANEL_ALLOW_WEBSOCKET_ORIGIN', '*')

# --- STATE MANAGEMENT ---
# Track selected pollutant for detailed view - using simple variables
selected_pollutant = 'AQI'
current_view = 'dashboard'

# --- OPTIMIZED DATA LOADING FUNCTIONS ---
def load_latest_data():
    """Load latest air quality data from SQLite database - optimized for memory"""
    conn = sqlite3.connect("air_quality.sqlite")
    # Only get the latest reading for each site using SQL to reduce memory usage
    query = """
    SELECT * FROM defra_uk_air_quality 
    WHERE (site, datetime) IN (
        SELECT site, MAX(datetime) 
        FROM defra_uk_air_quality 
        GROUP BY site
    )
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df

def load_historical_data_sample(site=None, limit=1000):
    """Load sampled historical data for trends - memory optimized"""
    conn = sqlite3.connect("air_quality.sqlite")
    if site:
        # Load recent data for specific site
        query = """
        SELECT * FROM defra_uk_air_quality 
        WHERE site = ? 
        ORDER BY datetime DESC 
        LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(site, limit))
    else:
        # Load sample of recent data across all sites
        query = """
        SELECT * FROM defra_uk_air_quality 
        ORDER BY datetime DESC 
        LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df.sort_values("datetime")

def get_cities_list():
    """Get list of cities without loading full dataset"""
    conn = sqlite3.connect("air_quality.sqlite")
    cities_df = pd.read_sql_query("SELECT DISTINCT site FROM defra_uk_air_quality ORDER BY site", conn)
    conn.close()
    return sorted(cities_df["site"].tolist())

# Load minimal data at startup
latest_data = load_latest_data()
cities = get_cities_list()

# --- AQI CALCULATION FUNCTIONS ---
def calc_aqi(pm25):
    """Calculate AQI based on PM2.5 using US EPA standards"""
    if pm25 <= 12:
        return int(pm25 / 12 * 50)
    elif pm25 <= 35.4:
        return int(50 + (pm25-12)/(35.4-12)*50)
    elif pm25 <= 55.4:
        return int(100 + (pm25-35.4)/(55.4-35.4)*50)
    elif pm25 <= 150.4:
        return int(150 + (pm25-55.4)/(150.4-55.4)*100)
    elif pm25 <= 250.4:
        return int(200 + (pm25-150.4)/(250.4-150.4)*100)
    elif pm25 <= 350.4:
        return int(300 + (pm25-250.4)/(350.4-250.4)*100)
    elif pm25 <= 500.4:
        return int(400 + (pm25-350.4)/(500.4-350.4)*100)
    else:
        return 500

def get_aqi_status(aqi):
    """Get AQI status, emoji, and color"""
    if aqi <= 50:
        return ("Good", "😊", "#00e400", "#e8f5e8")
    elif aqi <= 100:
        return ("Moderate", "😐", "#ff8c00", "#fff3e0")
    elif aqi <= 150:
        return ("Unhealthy for Sensitive Groups", "😷", "#ff7e00", "#fff3e0")
    elif aqi <= 200:
        return ("Unhealthy", "😷", "#ff0000", "#ffebee")
    elif aqi <= 300:
        return ("Very Unhealthy", "🤢", "#8f3f97", "#f3e5f5")
    else:
        return ("Hazardous", "☠️", "#7e0023", "#fce4ec")

def get_pollutant_status(pollutant, value):
    """Get pollutant status, color, and background color based on value"""
    if pollutant == 'PM2.5':
        if value <= 12:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 35.4:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 55.4:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 150.4:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 250.4:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    elif pollutant == 'PM10':
        if value <= 54:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 154:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 254:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 354:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 424:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    elif pollutant == 'NO2':
        if value <= 53:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 100:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 360:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 649:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 1249:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    elif pollutant == 'O3':
        if value <= 54:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 70:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 85:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 105:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 200:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    elif pollutant == 'CO':
        if value <= 4.4:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 9.4:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 12.4:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 15.4:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 30.4:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    elif pollutant == 'SO2':
        if value <= 35:
            return 'Good', '#00e400', '#e8f5e8'
        elif value <= 75:
            return 'Moderate', '#ff8c00', '#fff3e0'  # Changed from yellow to orange
        elif value <= 185:
            return 'Poor', '#ff7e00', '#fff0e6'
        elif value <= 304:
            return 'Unhealthy', '#ff0000', '#ffe6e6'
        elif value <= 604:
            return 'Severe', '#8f3f97', '#f3e5f5'
        else:
            return 'Hazardous', '#7e0023', '#fce4ec'
    else:
        return ("Unknown", "#666666", "#f5f5f5")

def get_pollutant_info(pollutant):
    """Get pollutant information and description"""
    info = {
        'PM2.5': {
            'name': 'Particulate Matter (PM2.5)',
            'description': 'Fine particles with diameter less than 2.5 micrometers',
            'sources': 'Vehicle emissions, industrial processes, wildfires',
            'health_effects': 'Can penetrate deep into lungs, causing respiratory and cardiovascular issues',
            'unit': 'µg/m³',
            'icon': '🌫️'
        },
        'PM10': {
            'name': 'Particulate Matter (PM10)',
            'description': 'Coarse particles with diameter less than 10 micrometers',
            'sources': 'Dust, construction, agriculture, vehicle emissions',
            'health_effects': 'Can irritate eyes, nose, and throat',
            'unit': 'µg/m³',
            'icon': '🌫️'
        },
        'NO2': {
            'name': 'Nitrogen Dioxide (NO₂)',
            'description': 'A reddish-brown gas with a sharp, biting odor',
            'sources': 'Vehicle emissions, power plants, industrial facilities',
            'health_effects': 'Can cause respiratory problems and reduce lung function',
            'unit': 'ppb',
            'icon': '🚗'
        },
        'O3': {
            'name': 'Ozone (O₃)',
            'description': 'A gas formed when pollutants react in sunlight',
            'sources': 'Vehicle emissions, industrial processes, sunlight',
            'health_effects': 'Can cause breathing problems and aggravate asthma',
            'unit': 'ppb',
            'icon': '☀️'
        },
        'CO': {
            'name': 'Carbon Monoxide (CO)',
            'description': 'A colorless, odorless gas produced by incomplete combustion',
            'sources': 'Vehicle emissions, industrial processes, wildfires',
            'health_effects': 'Reduces oxygen delivery to body tissues',
            'unit': 'ppb',
            'icon': '🔥'
        },
        'SO2': {
            'name': 'Sulfur Dioxide (SO₂)',
            'description': 'A colorless gas with a pungent odor',
            'sources': 'Power plants, industrial facilities, volcanoes',
            'health_effects': 'Can cause respiratory problems and acid rain',
            'unit': 'ppb',
            'icon': '🏭'
        }
    }
    return info.get(pollutant, {})

# --- INTERACTIVE COMPONENTS ---
city_selector = pn.widgets.Select(
    name='Select City', 
    options=cities, 
    value=cities[0] if cities else None,
    width=300
)

# Pollutant selector for detailed views
pollutant_selector = pn.widgets.Select(
    name='Select Pollutant',
    options=['AQI', 'PM2.5', 'PM10', 'NO2', 'O3', 'CO', 'SO2'],
    value='AQI',
    width=200
)

# Create a JavaScript callback to sync HTML dropdown with Panel widget
dropdown_js = pn.pane.HTML("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const cityDropdown = document.getElementById('city-dropdown');
    if (cityDropdown) {
        cityDropdown.addEventListener('change', function() {
            const selectedCity = this.value;
            // This will trigger the Panel widget update
            window.parent.postMessage({
                type: 'city_change',
                city: selectedCity
            }, '*');
        });
    }
});
</script>
""")

time_range = pn.widgets.Select(
    name='Time Range',
    options=['Last 24 Hours', 'Last 7 Days', 'Last 30 Days'],
    value='Last 24 Hours',
    width=200
)

# --- MAP CREATION ---
def create_map(city=None):
    """Create interactive map with air quality data"""
    if city and city in latest_data['site'].values:
        # Filter data for selected city
        city_data = latest_data[latest_data['site'] == city].iloc[0]
        center_lat = city_data['latitude']
        center_lon = city_data['longitude']
        zoom = 11  # Closer zoom for selected city
    else:
        # Default UK view
        center_lat, center_lon, zoom = 54.5, -3, 5.5
    
    # Create map with all cities
    fig = px.scatter_map(
        latest_data,
        lat='latitude',
        lon='longitude',
        hover_name='site',
        hover_data=['pm25', 'pm10', 'no2', 'o3'],
        color='pm25',
        color_continuous_scale='RdYlGn_r',
        size='pm25',
        zoom=zoom,
        center={'lat': center_lat, 'lon': center_lon}
    )
    
    # Highlight selected city with larger, prominent marker
    if city and city in latest_data['site'].values:
        city_data = latest_data[latest_data['site'] == city].iloc[0]
        fig.add_trace(go.Scattermap(
            lat=[city_data['latitude']],
            lon=[city_data['longitude']],
            mode='markers',
            marker=dict(
                size=30,
                color='#ff0000',
                symbol='circle'
            ),
            name=city,
            showlegend=False,
            hovertemplate=f'<b>{city}</b><br>Selected City<br>PM2.5: {city_data["pm25"]:.1f} µg/m³<extra></extra>'
        ))
    
    fig.update_layout(
        map_style='carto-positron',
        height=450,
        margin={'l': 0, 'r': 0, 't': 30, 'b': 0},
        showlegend=False,
        coloraxis_showscale=False
    )
    
    return fig

# --- DETAILED POLLUTANT VIEW ---
def generate_monthly_graph_from_real_data(city, pollutant):
    """Generate monthly aggregated graph from real database data"""
    try:
        # Load historical data (sampled for memory efficiency)
        df = load_historical_data_sample(limit=2000)
        city_data = df[df['site'] == city].copy()
        
        if len(city_data) == 0:
            return None, None, None
        
        # Convert datetime and group by month
        city_data['datetime'] = pd.to_datetime(city_data['datetime'])
        city_data['month'] = city_data['datetime'].dt.month
        city_data['year'] = city_data['datetime'].dt.year
        
        # Get pollutant column name
        pollutant_col = pollutant.lower()
        
        # Group by month and calculate monthly averages
        monthly_data = city_data.groupby(['year', 'month'])[pollutant_col].mean().reset_index()
        
        # Create monthly averages across all years
        monthly_avg = monthly_data.groupby('month')[pollutant_col].mean().reset_index()
        
        # Get current value for scaling
        latest_data = city_data.sort_values('datetime').iloc[-1]
        current_value = latest_data[pollutant_col]
        
        # Calculate monthly factors relative to current value
        monthly_factors = {}
        for _, row in monthly_avg.iterrows():
            month = row['month']
            avg_value = row[pollutant_col]
            factor = avg_value / current_value if current_value > 0 else 1.0
            monthly_factors[month] = factor
        
        # Generate graph bars with realistic seasonal patterns
        graph_bars = []
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for i, month in enumerate(months, 1):
            factor = monthly_factors.get(i, 1.0)
            # Add some variation within each month (4 bars per month)
            for week in range(4):
                week_factor = factor * (0.8 + 0.4 * week / 3)  # Gradual increase within month
                height_percent = min(100, max(5, week_factor * 50))  # Scale to 5-100%
                value = current_value * week_factor
                
                graph_bars.append({
                    'height': height_percent,
                    'title': f"{month}: {value:.1f}",
                    'value': value
                })
        
        # Calculate stats
        all_values = [bar['value'] for bar in graph_bars]
        max_value = max(all_values)
        min_value = min(all_values)
        
        return graph_bars, max_value, min_value
        
    except Exception as e:
        print(f"Error generating monthly graph: {e}")
        return None, None, None

def create_detailed_pollutant_view(city, pollutant):
    """Create detailed pollutant view with real historical data from database"""
    # Load historical data for the specific city and pollutant (sampled for memory efficiency)
    df = load_historical_data_sample(site=city, limit=1500)
    city_data = df[df['site'] == city].copy()
    
    # Get latest data for current values
    latest_data = city_data.sort_values('datetime').iloc[-1]
    
    # Get pollutant info
    info = get_pollutant_info(pollutant)
    
    # Get current pollutant value and status
    pollutant_value = latest_data[pollutant.lower()]
    status, color, bg_color = get_pollutant_status(pollutant, pollutant_value)
    
    # Prepare data for the view
    data = {
        'value': pollutant_value,
        'unit': info['unit'],
        'status': status,
        'color': color,
        'icon': info['icon']
    }
    
    # Get historical data for the graph (all-time data)
    historical_data = city_data.copy()
    
    # Get realistic historical data for visualization
    historical_data['date'] = historical_data['datetime'].dt.date
    daily_data = historical_data.groupby('date')[pollutant.lower()].mean().reset_index()
    
    # Use systematic sampling to show realistic trends
    # Take every nth data point to get a good representation
    if len(daily_data) > 200:
        step = len(daily_data) // 200
        sampled_data = daily_data.iloc[::step].copy()
    elif len(daily_data) > 100:
        step = len(daily_data) // 100
        sampled_data = daily_data.iloc[::step].copy()
    else:
        sampled_data = daily_data.copy()
    
    sampled_data = sampled_data.sort_values('date')  # Sort by date for proper timeline
    sampled_data['date'] = pd.to_datetime(sampled_data['date'])
    
    # Prepare graph data
    graph_data = []
    for _, row in sampled_data.iterrows():
        graph_data.append({
            'date': row['date'],
            'value': row[pollutant.lower()]
        })
    
    # Calculate stats for the graph
    if graph_data:
        values = [d['value'] for d in graph_data]
        max_value = max(values)
        min_value = min(values)
        current_value = pollutant_value
    else:
        max_value = pollutant_value * 1.2
        min_value = pollutant_value * 0.8
        current_value = pollutant_value
    
    # Generate graph HTML with real data
    graph_html = generate_real_historical_graph(graph_data, pollutant, data)
    
    # Create the detailed view HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{pollutant} Details for {city}</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                .container {{ 
                    max-width: 1200px;
                    margin: 0 auto; 
                    background: white; 
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, {color} 0%, {color}dd 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    font-size: 2.5rem;
                    margin-bottom: 10px;
                    font-weight: 600;
                }}
                .header p {{
                    font-size: 1.2rem;
                    opacity: 0.9;
                }}
                .main-content {{
                    padding: 40px;
                    background: linear-gradient(135deg, {color}15 0%, #ffffff 100%); 
                    border: 2px solid {color};
                    border-radius: 15px;
                    padding: 30px 25px; 
                    margin-bottom: 30px; 
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }}
                .current-level-section {{
                    margin-bottom: 40px;
                }}
                .current-level-title {{
                    font-size: 1.8rem;
                    color: #333;
                    margin-bottom: 10px;
                    font-weight: 600;
                }}
                .current-level-subtitle {{
                    font-size: 1.2rem;
                    color: #666;
                    margin-bottom: 30px;
                }}
                .main-display {{
                    background: linear-gradient(135deg, {color} 0%, {color}dd 100%);
                    color: white;
                    border-radius: 20px;
                    padding: 30px;
                    margin: 20px 0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 15px;
                    box-shadow: 0 10px 30px {color}40;
                }}
                .pollutant-icon {{
                    font-size: 3rem;
                    margin-bottom: 10px;
                }}
                .pollutant-value {{
                    font-size: 3.5rem;
                    font-weight: 700;
                    display: flex;
                    align-items: baseline;
                    gap: 10px;
                }}
                .pollutant-unit {{
                    font-size: 1.5rem;
                    opacity: 0.8;
                }}
                .status-badge {{
                    background: {color}; 
                    color: white;
                    padding: 8px 20px; 
                    border-radius: 25px; 
                    font-weight: 600;
                    font-size: 1.1rem;
                }}
                .last-updated {{
                    font-size: 0.9rem;
                    opacity: 0.8;
                }}
                .aqi-scale {{
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .scale-bar {{
                    display: flex;
                    height: 6px;
                    border-radius: 3px;
                    overflow: hidden;
                    margin-bottom: 8px;
                }}
                .scale-segment {{
                    flex: 1;
                    height: 100%;
                }}
                .scale-labels {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 0.75rem;
                    color: #666;
                    font-weight: 500;
                }}
                .good {{ background: #00e400; }}
                .moderate {{ background: #ff8c00; }}
                .poor {{ background: #ff7e00; }}
                .unhealthy {{ background: #ff0000; }}
                .severe {{ background: #8f3f97; }}
                .hazardous {{ background: #7e0023; }}
                .graph-section {{
                    margin-top: 40px;
                }}
                .graph-title-section {{
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .graph-title {{
                    font-size: 1.5rem;
                    color: #333;
                    font-weight: 600;
                }}
                .graph-container {{
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    margin: 20px 0;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                    position: relative;
                    height: 300px;
                    overflow-x: auto;
                }}
                .graph-bars {{
                    display: flex;
                    gap: 2px;
                    align-items: end;
                    height: 200px;
                    max-width: 100%;
                    margin: 0 auto;
                    position: relative;
                    padding: 0 10px;
                }}
                .graph-bar {{
                    background: linear-gradient(to top, #0066cc, #0099ff);
                    border-radius: 3px 3px 0 0;
                    min-width: 8px;
                    opacity: 0.9;
                    transition: all 0.3s ease;
                    position: relative;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .graph-bar:hover {{
                    transform: translateY(-2px);
                    opacity: 1;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }}
                .graph-y-labels {{
                    position: absolute;
                    left: 10px;
                    top: 0;
                    height: 200px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    font-size: 0.8rem;
                    color: #666;
                    font-weight: 500;
                }}
                .graph-labels {{
                    display: flex;
                    justify-content: space-between;
                    margin-top: 10px;
                    font-size: 0.8rem;
                    color: #666;
                    font-weight: 500;
                }}
                .graph-stats {{
                    display: flex;
                    justify-content: space-around;
                    margin-top: 20px;
                    gap: 20px;
                }}
                .stat-box {{
                    background: white;
                    border: 2px solid #4CAF50;
                    border-radius: 10px;
                    padding: 15px;
                    text-align: center;
                    flex: 1;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .stat-value {{
                    font-size: 1.5rem;
                    font-weight: 700;
                    color: #4CAF50;
                    margin-bottom: 5px;
                }}
                .stat-label {{
                    font-size: 0.9rem;
                    color: #666;
                    font-weight: 500;
                }}
                .sources-section {{
                    margin-top: 40px;
                }}
                .sources-title {{
                    font-size: 1.5rem;
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                    font-weight: 600;
                }}
                .sources-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }}
                .source-card {{ 
                    background: #f8f9fa; 
                    border-radius: 12px;
                    padding: 25px; 
                    border-left: 4px solid {color};
                    box-shadow: 0 3px 10px rgba(0,0,0,0.08);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                    text-align: center;
                }}
                .source-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                }}
                .source-icon {{
                    font-size: 2.5rem;
                    margin-bottom: 15px;
                    display: block;
                }}
                .source-card h3 {{
                    color: #333;
                    font-size: 1.2rem;
                    margin-bottom: 10px;
                    font-weight: 600;
                }}
                .source-card p {{
                    color: #666;
                    font-size: 0.9rem;
                    line-height: 1.5;
                }}
                .close-btn {{ 
                    background: linear-gradient(135deg, {color} 0%, {color}dd 100%); 
                    color: white; 
                    border: none; 
                    padding: 12px 30px; 
                    border-radius: 25px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 8px {color}40;
                }}
                .close-btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px {color}60;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{info['name']} Level</h1>
                    <p>{city}, United Kingdom</p>
                </div>
                
                <div class="main-content">
                    <!-- Current Level Section -->
                    <div class="current-level-section">
                        <h2 class="current-level-title">What is the Current {pollutant} Level?</h2>
                        <p class="current-level-subtitle">{city}</p>
                        
                        <div class="main-display">
                            <span class="pollutant-icon">{data['icon']}</span>
                            <div class="pollutant-value">{data['value']}<span class="pollutant-unit">{data['unit']}</span></div>
                            <div class="status-badge">{data['status']}</div>
                            <p class="last-updated">Last Updated: Recent</p>
                        </div>
                        
                        <div class="aqi-scale">
                            <h3 style="margin-bottom: 12px; color: #333; font-size: 1rem;">Air Quality Scale</h3>
                            <div class="scale-bar">
                                <div class="scale-segment good"></div>
                                <div class="scale-segment moderate"></div>
                                <div class="scale-segment poor"></div>
                                <div class="scale-segment unhealthy"></div>
                                <div class="scale-segment severe"></div>
                                <div class="scale-segment hazardous"></div>
                            </div>
                            <div class="scale-labels">
                                <span>Good</span>
                                <span>Moderate</span>
                                <span>Poor</span>
                                <span>Unhealthy</span>
                                <span>Severe</span>
                                <span>Hazardous</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Graph Section -->
                    <div class="graph-section">
                        <div class="graph-title-section">
                            <h3 class="graph-title">{pollutant} Historical Data (All-Time)</h3>
                        </div>
                        {graph_html}
                    </div>
                    
                    <!-- Sources Section -->
                    <div class="sources-section">
                        <h3 class="sources-title">Where Does {pollutant} Come From?</h3>
                        <div class="sources-grid">
                            <div class="source-card">
                                <span class="source-icon">🚗</span>
                                <h3>Vehicle Emissions</h3>
                                <p>Diesel and gasoline vehicles release {pollutant} through exhaust fumes and brake wear.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🏭</span>
                                <h3>Industrial Processes</h3>
                                <p>Factories and power plants emit {pollutant} during manufacturing and energy production.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🔥</span>
                                <h3>Combustion Activities</h3>
                                <p>Burning of fuels, waste, and biomass releases {pollutant} into the atmosphere.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🌫️</span>
                                <h3>Natural Sources</h3>
                                <p>Dust storms, wildfires, and volcanic eruptions contribute to {pollutant} levels.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🏗️</span>
                                <h3>Construction</h3>
                                <p>Building activities, demolition, and road construction generate {pollutant} dust.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🌾</span>
                                <h3>Agriculture</h3>
                                <p>Farming activities, crop burning, and livestock operations produce {pollutant}.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; padding: 30px;">
                    <button class="close-btn" onclick="window.close()">Close Window</button>
                </div>
            </div>
        </body>
    </html>
    """
    
    return html_content

def generate_real_historical_graph(graph_data, pollutant, data):
    """Generate real historical graph HTML from database data"""
    if not graph_data:
        return "<p>No historical data available</p>"
    
    # Calculate graph dimensions
    values = [d['value'] for d in graph_data]
    max_val = max(values)
    min_val = min(values)
    value_range = max_val - min_val if max_val != min_val else max_val
    
    # Generate bars HTML
    bars_html = ""
    for i, point in enumerate(graph_data):
        # Calculate bar height (0-100%)
        if value_range > 0:
            height_percent = ((point['value'] - min_val) / value_range) * 100
        else:
            height_percent = 50  # Default height if all values are the same
        
        # Format date for display
        date_str = point['date'].strftime('%b %d')
        
        bars_html += f"""
        <div class="graph-bar" style="height: {height_percent}%;" 
             title="{date_str}: {point['value']:.1f} {data['unit']}"></div>
        """
    
    # Generate labels
    labels_html = ""
    for point in graph_data:
        date_str = point['date'].strftime('%b %d')
        labels_html += f'<span>{date_str}</span>'
    
    # Generate Y-axis labels
    y_labels = []
    for i in range(5):
        value = min_val + (value_range * i / 4)
        y_labels.append(f'{value:.1f}')
    
    y_labels_html = ""
    for label in reversed(y_labels):
        y_labels_html += f'<span>{label}</span>'
    
    # Calculate stats
    current_value = data['value']
    max_value = max_val
    min_value = min_val
    
    return f"""
    <div class="graph-container">
        <div class="graph-y-labels">
            {y_labels_html}
        </div>
        <div class="graph-bars">
            {bars_html}
        </div>
        <div class="graph-labels">
            {labels_html}
        </div>
    </div>
    <div class="graph-stats">
        <div class="stat-box">
            <div class="stat-value">{max_value:.1f}</div>
            <div class="stat-label">Max Value</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{min_value:.1f}</div>
            <div class="stat-label">Min Value</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{current_value:.1f}</div>
            <div class="stat-label">Current</div>
        </div>
    </div>
    """

# --- AQI CARD CREATION ---
def create_aqi_card(city):
    """Create AQI status card"""
    if city not in latest_data['site'].values:
        return "City data not available"
    
    city_data = latest_data[latest_data['site'] == city].iloc[0]
    aqi = calc_aqi(city_data['pm25'])
    status, emoji, color, bg_color = get_aqi_status(aqi)
    
    # Format last updated time
    last_updated = city_data['datetime'].strftime("%d %b %H:%M")
    
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 50%, #e9ecef 100%);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        margin: -80px 0 20px 0;
        position: relative;
        z-index: 10;
        width: 100%;
        color: #333;
        min-height: 120px;
    ">
        <!-- Header - Left aligned -->
        <div style="text-align: left; margin-bottom: 15px;">
            <h2 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Real-time Air Quality Data</h2>
            <p style="margin: 0; color: #666; font-size: 0.9rem;">{city}, United Kingdom • Last Updated: {last_updated}</p>
        </div>
        
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <!-- Left side - AQI and PM values -->
            <div style="flex: 3; display: flex; gap: 40px; align-items: center;">
                <!-- AQI Section -->
                <div style="text-align: left;">
                    <div style="font-size: 0.9rem; color: #666; margin-bottom: 3px;">Live AQI</div>
                    <div style="font-size: 3.5rem; font-weight: bold; color: {color}; margin-bottom: 3px;">{aqi}</div>
                    <div style="font-size: 1rem; font-weight: 600; color: #333; margin-bottom: 3px;">Air Quality is</div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: {color};">{status}</div>
                </div>
                
                <!-- PM Values -->
                <div style="text-align: left; display: flex; gap: 30px;">
                    <div>
                        <div style="font-size: 0.9rem; color: #666; margin-bottom: 2px;">PM10</div>
                        <div style="font-size: 1.1rem; font-weight: bold; color: #333;">{city_data['pm10']:.1f} µg/m³</div>
                    </div>
                    <div>
                        <div style="font-size: 0.9rem; color: #666; margin-bottom: 2px;">PM2.5</div>
                        <div style="font-size: 1.1rem; font-weight: bold; color: #333;">{city_data['pm25']:.1f} µg/m³</div>
                    </div>
                </div>
            </div>
            
            <!-- Right side - Weather card -->
            <div style="flex: 1; background: linear-gradient(135deg, #e3f2fd, #bbdefb); border-radius: 12px; padding: 15px; border: 1px solid #e0e0e0;">
                <div style="text-align: center;">
                    <div style="font-size: 1.3rem; margin-bottom: 3px;">☁️</div>
                    <div style="font-size: 1.3rem; font-weight: bold; color: #333; margin-bottom: 3px;">{city_data['temperature']:.1f}°C</div>
                    <div style="font-size: 0.8rem; color: #666; margin-bottom: 2px;">Humidity: {city_data['humidity']:.1f}%</div>
                    <div style="font-size: 0.8rem; color: #666;">Wind: 14 km/h</div>
                </div>
            </div>
        </div>
        
        <!-- Compact AQI Scale Bar -->
        <div style="margin-top: 15px;">
            <div style="display: flex; height: 4px; border-radius: 2px; overflow: hidden; margin-bottom: 6px;">
                <div style="flex: 1; background: #00e400;"></div>
                <div style="flex: 1; background: #ff8c00;"></div>
                <div style="flex: 1; background: #ff7e00;"></div>
                <div style="flex: 1; background: #ff0000;"></div>
                <div style="flex: 1; background: #8f3f97;"></div>
                <div style="flex: 1; background: #7e0023;"></div>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="font-size: 0.65rem; color: #666;">Good</span>
                <span style="font-size: 0.65rem; color: #666;">Moderate</span>
                <span style="font-size: 0.65rem; color: #666;">Poor</span>
                <span style="font-size: 0.65rem; color: #666;">Unhealthy</span>
                <span style="font-size: 0.65rem; color: #666;">Severe</span>
                <span style="font-size: 0.65rem; color: #666;">Hazardous</span>
            </div>
        </div>
    </div>
    """
    
    return card_html

# --- TREND CHARTS ---
def create_trend_chart(city, time_range):
    """Create AQI trend chart"""
    # Load historical data for the specific city (memory optimized)
    df = load_historical_data_sample(site=city, limit=1000)
    city_data = df[df['site'] == city].copy()
    
    if city_data.empty:
        return go.Figure()
    
    if time_range == 'Last 24 Hours':
        cutoff = datetime.now() - timedelta(hours=24)
    elif time_range == 'Last 7 Days':
        cutoff = datetime.now() - timedelta(days=7)
    else:  # Last 30 Days
        cutoff = datetime.now() - timedelta(days=30)
    
    city_data = city_data[city_data['datetime'] >= cutoff].sort_values('datetime')
    
    if city_data.empty:
        return go.Figure()
    
    # Calculate AQI for each data point
    city_data['aqi'] = city_data['pm25'].apply(calc_aqi)
    
    fig = go.Figure()
    
    # Add AQI line
    fig.add_trace(go.Scatter(
        x=city_data['datetime'],
        y=city_data['aqi'],
        mode='lines+markers',
        name='AQI',
        line=dict(color='#667eea', width=3),
        marker=dict(size=6)
    ))
    
    # Add PM2.5 line
    fig.add_trace(go.Scatter(
        x=city_data['datetime'],
        y=city_data['pm25'],
        mode='lines+markers',
        name='PM2.5 (µg/m³)',
        line=dict(color='#ff6b6b', width=2),
        marker=dict(size=4),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title=f'AQI Trend - {city}',
        height=300,
        xaxis_title='Time',
        yaxis_title='AQI',
        yaxis2=dict(title='PM2.5 (µg/m³)', overlaying='y', side='right'),
        hovermode='x unified',
        showlegend=True,
        legend=dict(x=0.02, y=0.98)
    )
    
    return fig

def create_pollutants_chart(city):
    """Create pollutants comparison chart"""
    if city not in latest_data['site'].values:
        return go.Figure()
    
    city_data = latest_data[latest_data['site'] == city].iloc[0]
    
    pollutants = ['PM2.5', 'PM10', 'NO₂', 'O₃']
    values = [city_data['pm25'], city_data['pm10'], city_data['no2'], city_data['o3']]
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4']
    
    fig = go.Figure(data=[
        go.Bar(
            x=pollutants,
            y=values,
            marker_color=colors,
            text=[f'{v:.1f}' for v in values],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title=f'Current Pollutant Levels - {city}',
        height=300,
        yaxis_title='Concentration (µg/m³)',
        showlegend=False
    )
    
    return fig

# --- DASHBOARD LAYOUT ---
# Create a header with Panel widgets properly embedded
header = pn.Row(
    pn.pane.HTML("""
        <div style="
            background: white;
            color: #333;
            padding: 8px 0;
            margin: 0;
            border-bottom: 1px solid #e0e0e0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            <div style="display: flex; align-items: center; justify-content: flex-start; max-width: 1200px; margin: 0 auto; gap: 30px;">
                <div style="display: flex; align-items: center;">
                    <h1 style="margin: 0; font-size: 1.4rem; font-weight: 700; color: #333;">UK AIR QUALITY DASHBOARD</h1>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="position: relative;">
                        <input type="text" placeholder="Search any Location, City..." 
                               style="padding: 8px 12px 8px 35px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 14px; width: 250px; background-image: url('data:image/svg+xml;utf8,<svg fill=&quot;%2399a1b3&quot; height=&quot;16&quot; viewBox=&quot;0 0 24 24&quot; width=&quot;16&quot; xmlns=&quot;http://www.w3.org/2000/svg&quot;><path d=&quot;M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99a1 1 0 001.41-1.41l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z&quot;></path></svg>'); background-repeat: no-repeat; background-position: 10px center;"
                        />
                    </div>
                </div>
            </div>
        </div>
    """),
    city_selector,
    time_range,
    align='center'
)

# Controls row is no longer needed since dropdowns are in header
controls = pn.Row(align='center')

# Map section
map_pane = pn.pane.Plotly(create_map(cities[0] if cities else None), height=450)

# AQI Card (will be updated dynamically) - centered like AQI.in
aqi_card = pn.pane.HTML(create_aqi_card(cities[0] if cities else None))

# Create pollutant cards function
def create_historical_aqi_graph(city):
    """Create historical AQI graph for a city - synchronized with original data"""
    if not city:
        return None
    
    # Get historical data for the city (sampled for memory efficiency)
    df = load_historical_data_sample(site=city, limit=1000)
    city_data = df[df['site'] == city].copy()
    
    if city_data.empty:
        # If no data for this city, create a placeholder graph
        fig = go.Figure()
        fig.add_annotation(
            text=f"No historical data available for {city}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=200,
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    # Convert datetime to datetime
    city_data['datetime'] = pd.to_datetime(city_data['datetime'])
    
    # Sort by datetime
    city_data = city_data.sort_values('datetime')
    
    # Get the last 24 hours of data for better synchronization
    latest_time = city_data['datetime'].max()
    cutoff_time = latest_time - timedelta(hours=24)
    recent_data = city_data[city_data['datetime'] >= cutoff_time].copy()
    
    # If we don't have 24 hours of data, get the last 20 data points
    if len(recent_data) < 5:
        recent_data = city_data.tail(20).copy()
    
    if recent_data.empty:
        # Still no data, create placeholder
        fig = go.Figure()
        fig.add_annotation(
            text=f"No data available for {city}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=200,
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    # Calculate AQI for each row
    recent_data['aqi'] = recent_data['pm25'].apply(calc_aqi)
    
    # Create the graph
    fig = go.Figure()
    
    # Add bar chart with dark green styling
    fig.add_trace(go.Bar(
        x=recent_data['datetime'],
        y=recent_data['aqi'],
        marker_color='#2e7d32',
        name='AQI',
        hovertemplate='<b>Time:</b> %{x}<br><b>AQI:</b> %{y}<extra></extra>',
        marker_line_width=0,
        opacity=0.9
    ))
    
    # Update layout - centered and properly formatted
    fig.update_layout(
        title=None,
        xaxis_title=None,
        yaxis_title=None,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=10),
        margin=dict(l=40, r=20, t=20, b=40),
        height=200,
        showlegend=False,
        xaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            tickformat='%m-%d %H:%M',
            tickmode='auto',
            nticks=6,
            tickfont=dict(size=9),
            tickangle=0
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            range=[0, max(recent_data['aqi']) * 1.1 if max(recent_data['aqi']) > 0 else 50],
            tickfont=dict(size=9),
            tickmode='linear',
            dtick=20
        )
    )
    
    return fig

def create_aqi_index():
    """Create AQI index scale component"""
    return f"""
    <div style="
        margin: 30px auto;
        max-width: 1200px;
        width: 100%;
        padding: 30px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    ">
        <div style="text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; color: #333; font-size: 1.8rem; font-weight: 600;">Air Quality Index (AQI) Scale</h2>
            <p style="margin: 8px 0 0 0; color: #666; font-size: 1rem;">Know about the category of air quality index (AQI) your ambient air falls in and what it implies.</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
            <!-- Good -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #00e400;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #00e400;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">😊</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Good</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(0 to 50)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">The air is fresh and free from toxins. Enjoy outdoor activities without any health concerns.</p>
                </div>
            </div>
            
            <!-- Moderate -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #ff8c00;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #ff8c00;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #333;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">😐</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Moderate</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(51 to 100)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">Air quality is acceptable for most, but sensitive individuals might experience mild discomfort.</p>
                </div>
            </div>
            
            <!-- Poor -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #ff7e00;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #ff7e00;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">😷</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Poor</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(101 to 150)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">Breathing may become slightly uncomfortable, especially for those with respiratory issues.</p>
                </div>
            </div>
            
            <!-- Unhealthy -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #ff0000;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #ff0000;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">😷</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Unhealthy</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(151 to 200)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">This air quality is particularly risky for children, pregnant women, and the elderly. Limit outdoor activities.</p>
                </div>
            </div>
            
            <!-- Severe -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #8f3f97;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #8f3f97;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">🤢</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Severe</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(201 to 300)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">Prolonged exposure can cause chronic health issues or organ damage. Avoid outdoor activities.</p>
                </div>
            </div>
            
            <!-- Hazardous -->
            <div style="
                background: #f8f9fa;
                border-left: 5px solid #7e0023;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            ">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #7e0023;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 1.2rem;
                ">☠️</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; color: #333; font-size: 1.2rem; font-weight: 600;">Hazardous</h3>
                    <p style="margin: 0 0 3px 0; color: #666; font-size: 0.9rem; font-weight: 500;">(301+)</p>
                    <p style="margin: 0; color: #333; font-size: 0.9rem; line-height: 1.4;">Dangerously high pollution levels. Life-threatening health risks with prolonged exposure. Stay indoors and take precautions.</p>
                </div>
            </div>
        </div>
    </div>
    """

def create_pollutant_cards(city):
    """Create pollutant cards like AQI.in - improved layout with click functionality"""
    if city not in latest_data['site'].values:
        return "City data not available"
    
    city_data = latest_data[latest_data['site'] == city].iloc[0]
    
    # Get pollutant values and status
    pm25_value = city_data['pm25']
    pm10_value = city_data['pm10']
    no2_value = city_data['no2']
    o3_value = city_data['o3']
    co_value = city_data.get('co', 95)
    so2_value = city_data.get('so2', 0)
    
    # Get status and colors for each pollutant
    pm25_status, pm25_color, _ = get_pollutant_status('PM2.5', pm25_value)
    pm10_status, pm10_color, _ = get_pollutant_status('PM10', pm10_value)
    no2_status, no2_color, _ = get_pollutant_status('NO2', no2_value)
    o3_status, o3_color, _ = get_pollutant_status('O3', o3_value)
    
    # Create JavaScript for pollutant detail view with real data
    js_code = f"""
    <script>
    // Store pollutant data
    const pollutantData = {{
        'PM2.5': {{ value: {pm25_value:.1f}, status: '{pm25_status}', color: '{pm25_color}', unit: 'µg/m³', icon: '🌫️' }},
        'PM10': {{ value: {pm10_value:.1f}, status: '{pm10_status}', color: '{pm10_color}', unit: 'µg/m³', icon: '🌫️' }},
        'NO2': {{ value: {no2_value:.0f}, status: '{no2_status}', color: '{no2_color}', unit: 'ppb', icon: '🚗' }},
        'O3': {{ value: {o3_value:.0f}, status: '{o3_status}', color: '{o3_color}', unit: 'ppb', icon: '☀️' }},
        'CO': {{ value: {co_value:.0f}, status: 'Good', color: '#00e400', unit: 'ppb', icon: '🔥' }},
        'SO2': {{ value: {so2_value:.0f}, status: 'Good', color: '#00e400', unit: 'ppb', icon: '🏭' }}
    }};
    
    const pollutantInfo = {{
        'PM2.5': {{
            name: 'Particulate Matter (PM2.5)',
            description: 'Fine particles with diameter less than 2.5 micrometers that can penetrate deep into the lungs.',
            sources: 'Vehicle emissions, industrial processes, wildfires, and combustion activities.',
            health_effects: 'Can cause respiratory and cardiovascular issues, especially in sensitive individuals.'
        }},
        'PM10': {{
            name: 'Particulate Matter (PM10)',
            description: 'Coarse particles with diameter less than 10 micrometers that can be inhaled.',
            sources: 'Dust, construction activities, agriculture, vehicle emissions, and industrial processes.',
            health_effects: 'Can irritate eyes, nose, and throat, and cause respiratory problems.'
        }},
        'NO2': {{
            name: 'Nitrogen Dioxide (NO₂)',
            description: 'A reddish-brown gas with a sharp, biting odor that forms from combustion processes.',
            sources: 'Vehicle emissions, power plants, industrial facilities, and heating systems.',
            health_effects: 'Can cause respiratory problems, reduce lung function, and aggravate asthma.'
        }},
        'O3': {{
            name: 'Ozone (O₃)',
            description: 'A gas formed when pollutants react in sunlight, creating ground-level ozone.',
            sources: 'Vehicle emissions, industrial processes, and chemical reactions in sunlight.',
            health_effects: 'Can cause breathing problems, aggravate asthma, and reduce lung function.'
        }},
        'CO': {{
            name: 'Carbon Monoxide (CO)',
            description: 'A colorless, odorless gas produced by incomplete combustion of carbon-based fuels.',
            sources: 'Vehicle emissions, industrial processes, wildfires, and heating systems.',
            health_effects: 'Reduces oxygen delivery to body tissues and can cause headaches and dizziness.'
        }},
        'SO2': {{
            name: 'Sulfur Dioxide (SO₂)',
            description: 'A colorless gas with a pungent odor that forms from burning sulfur-containing fuels.',
            sources: 'Power plants, industrial facilities, volcanoes, and some heating systems.',
            health_effects: 'Can cause respiratory problems, acid rain, and damage to vegetation.'
        }}
    }};
    
    function showPollutantDetail(pollutant, city) {{
        const data = pollutantData[pollutant];
        const info = pollutantInfo[pollutant];
        
        if (!data || !info) {{
            alert('Data not available for ' + pollutant);
            return;
        }}
        
        const detailHtml = createPollutantDetailHTML(pollutant, city, data, info);
        const newWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes');
        newWindow.document.write(detailHtml);
        newWindow.document.close();
    }}
    
    function createPollutantDetailHTML(pollutant, city, data, info) {{
        return `
        <html>
        <head>
            <title>${{info.name}} - ${{city}} Air Quality</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
                    background: #f8f9fa; 
                    color: #333;
                    line-height: 1.6;
                }}
                .container {{ 
        max-width: 1200px;
                    margin: 0 auto; 
                    background: white; 
                    min-height: 100vh;
                    box-shadow: 0 0 20px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px 40px;
                    text-align: center;
                }}
                .header h1 {{ 
                    font-size: 2.5rem; 
                    font-weight: 700; 
                    margin-bottom: 10px;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{ 
                    font-size: 1.2rem; 
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .main-content {{
                    padding: 40px;
                }}
                .current-level-section {{
                    margin-bottom: 40px;
                }}
                .current-level-title {{
                    font-size: 1.8rem;
                    font-weight: 700;
                    color: #333;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .current-level-subtitle {{
                    font-size: 1.2rem;
                    color: #0066cc;
                    font-weight: 600;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .main-display {{ 
                    background: linear-gradient(135deg, ${{data.color}}15 0%, #ffffff 100%); 
                    border: 2px solid ${{data.color}};
        border-radius: 15px;
                    padding: 30px 25px; 
                    margin-bottom: 30px; 
                text-align: center;
                    position: relative;
                    overflow: hidden;
                    max-width: 400px;
                    margin-left: auto;
                    margin-right: auto;
                }}
                .main-display::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    right: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, ${{data.color}}08 0%, transparent 70%);
                    z-index: 0;
                }}
                .main-display > * {{ position: relative; z-index: 1; }}
                .pollutant-icon {{ 
                    font-size: 3rem; 
                    margin-bottom: 15px;
                    display: block;
                }}
                .pollutant-value {{ 
                    font-size: 3.5rem; 
                    font-weight: 800; 
                    color: ${{data.color}}; 
                    margin-bottom: 10px;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .pollutant-unit {{ 
                    font-size: 1.5rem; 
                    font-weight: 600; 
                    color: #666;
                    margin-left: 8px;
                }}
                .status-badge {{ 
                    background: ${{data.color}}; 
                color: white;
                    padding: 8px 20px; 
                    border-radius: 25px; 
                    font-size: 1rem; 
                    font-weight: 700; 
                    display: inline-block; 
                    margin-bottom: 15px;
                    box-shadow: 0 2px 8px ${{data.color}}40;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .last-updated {{ 
                    color: #666; 
                    font-size: 0.9rem;
                    font-weight: 500;
                }}
                .graph-section {{
                    background: white;
                    border-radius: 15px;
                    padding: 30px;
                    margin-bottom: 40px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                }}
                .graph-title {{
                    font-size: 1.4rem;
                    font-weight: 700;
                    color: #333;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .graph-container {{
                    background: white;
                border-radius: 12px;
                padding: 25px;
                    margin: 20px 0;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                    position: relative;
                    height: 300px;
                    overflow-x: auto;
                }}
                .graph-bars {{
                    display: flex;
                    gap: 2px;
                    align-items: end;
                    height: 200px;
                    max-width: 100%;
                    margin: 0 auto;
                    position: relative;
                    padding: 0 10px;
                }}
                .graph-bar {{
                    background: linear-gradient(to top, #0066cc, #0099ff);
                    border-radius: 3px 3px 0 0;
                    min-width: 8px;
                    opacity: 0.9;
                    transition: all 0.3s ease;
                    position: relative;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .graph-bar:hover {{
                    opacity: 1;
                    transform: scaleY(1.05);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }}
                .graph-axis {{
                    position: absolute;
                    left: 0;
                    right: 0;
                    height: 200px;
                    pointer-events: none;
                }}
                .graph-axis-line {{
                    position: absolute;
                    left: 0;
                    right: 0;
                    height: 1px;
                    background: #ddd;
                }}
                .graph-axis-line:nth-child(1) {{ top: 0; }}
                .graph-axis-line:nth-child(2) {{ top: 50px; }}
                .graph-axis-line:nth-child(3) {{ top: 100px; }}
                .graph-axis-line:nth-child(4) {{ top: 150px; }}
                .graph-axis-line:nth-child(5) {{ top: 200px; }}
                .graph-labels {{
                    display: flex;
                    justify-content: space-between;
                    margin-top: 15px;
                    font-size: 0.8rem;
                    color: #666;
                    font-weight: 500;
                }}
                .graph-y-labels {{
                    position: absolute;
                    left: -40px;
                    top: 0;
                    height: 200px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    font-size: 0.75rem;
                    color: #666;
                    font-weight: 500;
                }}
                .graph-title-section {{
                text-align: center;
                    margin-bottom: 20px;
                }}
                .graph-stats {{
                    display: flex;
                    justify-content: center;
                    gap: 30px;
                    margin-top: 20px;
                }}
                .stat-box {{
                    background: white;
                    border: 2px solid ${{data.color}};
                    border-radius: 8px;
                    padding: 10px 15px;
                    text-align: center;
                    min-width: 100px;
                }}
                .stat-value {{
                    font-size: 1.2rem;
                    font-weight: 700;
                    color: ${{data.color}};
                }}
                .stat-label {{
                    font-size: 0.8rem;
                    color: #666;
                    margin-top: 2px;
                }}
                .sources-section {{
                    margin-bottom: 40px;
                }}
                .sources-title {{
                    font-size: 1.6rem;
                    font-weight: 700;
                    color: #333;
                    margin-bottom: 30px;
                    text-align: center;
                }}
                .sources-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(3, 1fr); 
                    gap: 20px; 
                    margin-bottom: 40px; 
                }}
                .source-card {{ 
                    background: #f8f9fa; 
                border-radius: 12px;
                padding: 25px;
                    border-left: 4px solid ${{data.color}};
                    box-shadow: 0 3px 10px rgba(0,0,0,0.08);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                text-align: center;
                }}
                .source-card:hover {{
                    transform: translateY(-3px);
                    box-shadow: 0 6px 20px rgba(0,0,0,0.12);
                }}
                .source-icon {{ 
                    font-size: 2.5rem; 
                    margin-bottom: 15px;
                    display: block;
                }}
                .source-card h3 {{ 
                    font-size: 1.1rem; 
                    font-weight: 700; 
                    margin-bottom: 10px;
                    color: #333;
                }}
                .source-card p {{ 
                    color: #555; 
                    font-size: 0.9rem; 
                    line-height: 1.5;
                    font-weight: 400;
                }}
                .close-section {{ 
                    text-align: center; 
                    padding: 20px 0;
                    border-top: 1px solid #e0e0e0;
                }}
                .close-btn {{ 
                    background: linear-gradient(135deg, ${{data.color}} 0%, ${{data.color}}dd 100%); 
                color: white;
                    border: none; 
                    padding: 12px 30px; 
                    border-radius: 25px; 
                    font-size: 1rem; 
                    font-weight: 600; 
                    cursor: pointer;
                    transition: all 0.3s ease;
                    box-shadow: 0 3px 10px ${{data.color}}40;
                }}
                .close-btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px ${{data.color}}60;
                }}
                .aqi-scale {{
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .scale-bar {{
                    display: flex;
                    height: 6px;
                    border-radius: 3px;
                    overflow: hidden;
                    margin-bottom: 8px;
                }}
                .scale-segment {{
                    flex: 1;
                    height: 100%;
                }}
                .scale-labels {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 0.75rem;
                    color: #666;
                    font-weight: 500;
                }}
                .good {{ background: #00e400; }}
                .moderate {{ background: #ff8c00; }}
                .poor {{ background: #ff7e00; }}
                .unhealthy {{ background: #ff0000; }}
                .severe {{ background: #8f3f97; }}
                .hazardous {{ background: #7e0023; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>${{info.name}} Level</h1>
                    <p>${{city}}, United Kingdom</p>
            </div>
            
                <div class="main-content">
                    <!-- Current Level Section -->
                    <div class="current-level-section">
                        <h2 class="current-level-title">What is the Current ${{pollutant}} Level?</h2>
                        <p class="current-level-subtitle">${{city}}</p>
                        
                        <div class="main-display">
                            <span class="pollutant-icon">${{data.icon}}</span>
                            <div class="pollutant-value">${{data.value}}<span class="pollutant-unit">${{data.unit}}</span></div>
                            <div class="status-badge">${{data.status}}</div>
                            <p class="last-updated">Last Updated: Recent</p>
            </div>
            
                        <div class="aqi-scale">
                            <h3 style="margin-bottom: 12px; color: #333; font-size: 1rem;">Air Quality Scale</h3>
                            <div class="scale-bar">
                                <div class="scale-segment good"></div>
                                <div class="scale-segment moderate"></div>
                                <div class="scale-segment poor"></div>
                                <div class="scale-segment unhealthy"></div>
                                <div class="scale-segment severe"></div>
                                <div class="scale-segment hazardous"></div>
                            </div>
                            <div class="scale-labels">
                                <span>Good</span>
                                <span>Moderate</span>
                                <span>Poor</span>
                                <span>Unhealthy</span>
                                <span>Severe</span>
                                <span>Hazardous</span>
                            </div>
                        </div>
            </div>
            
                    <!-- Sources Section -->
                    <div class="sources-section">
                        <h3 class="sources-title">Where Does ${{pollutant}} Come From?</h3>
                        <div class="sources-grid">
                            <div class="source-card">
                                <span class="source-icon">🚗</span>
                                <h3>Vehicle Emissions</h3>
                                <p>Diesel and gasoline vehicles release ${{pollutant}} through exhaust fumes and brake wear.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🏭</span>
                                <h3>Industrial Processes</h3>
                                <p>Factories and power plants emit ${{pollutant}} during manufacturing and energy production.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🔥</span>
                                <h3>Combustion Activities</h3>
                                <p>Burning of fuels, waste, and biomass releases ${{pollutant}} into the atmosphere.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🌫️</span>
                                <h3>Natural Sources</h3>
                                <p>Dust storms, wildfires, and volcanic eruptions contribute to ${{pollutant}} levels.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🏗️</span>
                                <h3>Construction</h3>
                                <p>Building activities, demolition, and road construction generate ${{pollutant}} dust.</p>
                            </div>
                            <div class="source-card">
                                <span class="source-icon">🌾</span>
                                <h3>Agriculture</h3>
                                <p>Farming activities, crop burning, and livestock operations produce ${{pollutant}}.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="close-section">
                    <button class="close-btn" onclick="window.close()">← Close Window</button>
                </div>
            </div>
        </body>
        </html>
        `;
    }}
    </script>
    """
    
    cards_html = f"""
    {js_code}
    <div style="
        background: white;
        padding: 40px 60px;
        margin: 30px auto;
        max-width: 1400px;
        width: 100%;
    ">
        <div style="margin-bottom: 30px; text-align: center;">
            <h2 style="margin: 0; color: #333; font-size: 1.8rem; font-weight: 600;">Major Air Pollutants</h2>
            <p style="margin: 8px 0 0 0; color: #0066cc; font-size: 1.2rem; font-weight: 500;">{city}</p>
            <p style="margin: 8px 0 0 0; color: #666; font-size: 1rem;">Click on any pollutant card to view detailed information</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 25px; max-width: 1200px; margin: 0 auto;">
            <!-- PM2.5 Card -->
            <div onclick="showPollutantDetail('PM2.5', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid {pm25_color};
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                 cursor: pointer;
                 transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Particulate Matter</div>
                    <div style="font-size: 0.9rem; color: #666;">(PM2.5)</div>
                 </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{pm25_value:.1f} µg/m³</div>
                    <div style="font-size: 1.2rem; color: {pm25_color};">→</div>
                </div>
            </div>
            
            <!-- PM10 Card -->
            <div onclick="showPollutantDetail('PM10', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid {pm10_color};
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                 cursor: pointer;
                 transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Particulate Matter</div>
                    <div style="font-size: 0.9rem; color: #666;">(PM10)</div>
                 </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{pm10_value:.1f} µg/m³</div>
                    <div style="font-size: 1.2rem; color: {pm10_color};">→</div>
                </div>
            </div>
            
            <!-- CO Card -->
            <div onclick="showPollutantDetail('CO', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid #00e400;
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                cursor: pointer;
                transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Carbon Monoxide</div>
                    <div style="font-size: 0.9rem; color: #666;">(CO)</div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{co_value:.0f} ppb</div>
                    <div style="font-size: 1.2rem; color: #666;">→</div>
                </div>
            </div>
            
            <!-- SO2 Card -->
            <div onclick="showPollutantDetail('SO2', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid #00e400;
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                cursor: pointer;
                transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Sulfur Dioxide</div>
                    <div style="font-size: 0.9rem; color: #666;">(SO2)</div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{so2_value:.0f} ppb</div>
                    <div style="font-size: 1.2rem; color: #666;">↓</div>
                </div>
            </div>
            
            <!-- NO2 Card -->
            <div onclick="showPollutantDetail('NO2', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid {no2_color};
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                cursor: pointer;
                transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Nitrogen Dioxide</div>
                    <div style="font-size: 0.9rem; color: #666;">(NO2)</div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{no2_value:.0f} ppb</div>
                    <div style="font-size: 1.2rem; color: {no2_color};">→</div>
                </div>
            </div>
            
            <!-- O3 Card -->
            <div onclick="showPollutantDetail('O3', '{city}')" style="
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-left: 5px solid {o3_color};
                border-radius: 12px;
                padding: 25px 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                cursor: pointer;
                transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div style="font-size: 1.1rem; color: #333; font-weight: 500;">Ozone</div>
                    <div style="font-size: 0.9rem; color: #666;">(O3)</div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: #333;">{o3_value:.0f} ppb</div>
                    <div style="font-size: 1.2rem; color: {o3_color};">→</div>
                </div>
            </div>
        </div>
    </div>
    """
    
    return cards_html

# Create pollutant cards
pollutant_cards = pn.pane.HTML(create_pollutant_cards(cities[0] if cities else None))

# Create historical AQI graph with width control - centered
aqi_graph = pn.pane.Plotly(
    create_historical_aqi_graph(cities[0] if cities else None),
    width=1200,
    height=250,
    align='center'
)

# Create graph header
def create_graph_header(city):
    return f"""
    <div style="
        margin: 20px auto 0 auto;
        max-width: 1200px;
        width: 100%;
        padding: 20px 0;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <div style="text-align: left;">
                <p style="margin: 0; color: #666; font-size: 0.9rem; font-weight: 500;">AQI Graph</p>
                <h3 style="margin: 5px 0 0 0; color: #333; font-size: 1.4rem; font-weight: 600;">Historical Air Quality Data</h3>
                <p style="margin: 5px 0 0 0; color: #0066cc; font-size: 1rem; font-weight: 500;">{city}</p>
        </div>
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="display: flex; background: #f5f5f5; border-radius: 6px; padding: 2px;">
                <button style="
                        background: #007bff;
                        color: white;
                    border: none;
                        padding: 8px 12px;
                        border-radius: 4px;
                    cursor: pointer;
                        font-size: 0.8rem;
                        font-weight: 500;
                ">📊</button>
                <button style="
                        background: #e0e0e0;
                        color: #333;
                    border: none;
                        padding: 8px 12px;
                        border-radius: 4px;
                    cursor: pointer;
                        font-size: 0.8rem;
                ">📈</button>
            </div>
            <select style="
                    padding: 8px 12px;
                border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 0.9rem;
                background: white;
                    cursor: pointer;
            ">
                <option>24 Hours</option>
                <option>7 Days</option>
                <option>30 Days</option>
            </select>
            <select style="
                    padding: 8px 12px;
                border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 0.9rem;
                background: white;
                    cursor: pointer;
            ">
                <option>AQI</option>
                <option>PM2.5</option>
                <option>PM10</option>
            </select>
            </div>
        </div>
    </div>
    """

graph_header = pn.pane.HTML(create_graph_header(cities[0] if cities else None))

# Create dynamic content area for switching between dashboard and pollutant detail views
dynamic_content = pn.Column(
    name='dynamic_content',
    sizing_mode='stretch_width'
)

# Charts section with pollutant cards and graph as separate sections - properly centered
charts_row = pn.Column(
    pollutant_cards,
    graph_header,
    pn.Column(aqi_graph, align='center', width=1200),
    align='center',
    sizing_mode='stretch_width'
)

# Create AQI index component
aqi_index = pn.pane.HTML(create_aqi_index())

def create_city_cards():
    """Create city cards similar to aqi.in showing all UK cities"""
    # Load data for all cities
    df = load_latest_data()
    
    # Get unique sites (cities)
    cities = df['site'].unique()
    
    # City icons (landmarks for each city)
    city_icons = {
        'London': '🏰',  # Tower Bridge
        'Birmingham': '🏢',  # Rotunda
        'Manchester': '🏙️',  # Beetham Tower
        'Glasgow': '🎭',  # Clyde Auditorium
        'Leeds': '🏛️',  # Town Hall
        'Bristol': '🌉',  # Clifton Suspension Bridge
        'Liverpool': '⚓',  # Albert Dock
        'Newcastle': '🌉',  # Tyne Bridge
        'Sheffield': '🏭',  # Industrial heritage
        'Edinburgh': '🏰',  # Edinburgh Castle
        'Cardiff': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',  # Welsh flag
        'Belfast': '🍀',  # Northern Ireland
        'Nottingham': '🌳',  # Sherwood Forest
        'Southampton': '🚢',  # Port city
        'Oxford': '🎓',  # University
        'Cambridge': '🎓',  # University
        'Brighton': '🏖️',  # Seaside
        'Plymouth': '⚓',  # Naval port
        'York': '🏰',  # York Minster
        'Norwich': '🏛️',  # Cathedral
        'Bath': '🛁',  # Roman baths
        'Exeter': '🏛️',  # Cathedral
        'Coventry': '🏛️',  # Cathedral
        'Derby': '🏭',  # Industrial
        'Stoke': '🏺',  # Pottery
        'Wolverhampton': '🐺',  # Wolves
        'Reading': '📚',  # University
        'Preston': '🏛️',  # Guild Hall
        'Newport': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',  # Welsh
        'Swansea': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',  # Welsh
        'Bradford': '🏭',  # Industrial
        'Sunderland': '⚽',  # Football
        'Hull': '🐟',  # Fishing port
        'Leicester': '🦊',  # Foxes
        'Portsmouth': '⚓',  # Naval base
        'Bolton': '🏭',  # Industrial
        'Stockport': '🌉',  # Viaduct
        'Wigan': '🏭',  # Industrial
        'Middlesbrough': '🏭',  # Industrial
        'Blackpool': '🎡',  # Pleasure Beach
        'Warrington': '🌉',  # Bridge
        'Milton Keynes': '🛣️',  # Grid system
        'Northampton': '👢',  # Boots
        'Luton': '✈️',  # Airport
        'Swindon': '🚗',  # Car industry
        'Dundee': '🍊',  # Jute
        'Aberdeen': '🛢️',  # Oil
        'Inverness': '🏔️',  # Highlands
        'Perth': '🏛️',  # Fair City
    }
    
    cards_html = """
    <div style="
        background: white;
        border-radius: 15px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    ">
        <h2 style="
            color: #333;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 25px;
            text-align: center;
        ">United Kingdom's Metro Cities Air Quality Index</h2>
        
        <div style="
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        ">
    """
    
    for city in cities:
        city_data = df[df['site'] == city].iloc[0]
        
        # Calculate AQI
        aqi = calc_aqi(city_data['pm25'])
        aqi_status = get_aqi_status(aqi)
        
        # Get city icon
        icon = city_icons.get(city, '🏙️')
        
        # Format temperature and humidity with 1 decimal place
        temp = round(city_data.get('temperature', 20), 1)
        humidity = round(city_data.get('humidity', 65), 1)
        
        # Use gray/black colors for borders and text, but keep AQI badge colors
        border_color = "#666666"  # Gray border
        badge_color = aqi_status[2]  # AQI-based color for badge
        text_color = "#333333"    # Dark gray text
        
        cards_html += f"""
        <div style="
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border: 2px solid {border_color};
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        " onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" 
           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)'">
            
            <div style="
                position: absolute;
                top: 10px;
                right: 10px;
                font-size: 1.2rem;
                color: #666;
            ">→</div>
            
            <div style="
                display: flex;
                align-items: center;
                margin-bottom: 15px;
            ">
                <span style="
                    font-size: 2rem;
                    margin-right: 12px;
                ">{icon}</span>
                <div>
                    <h3 style="
                        margin: 0;
                        font-size: 1.3rem;
                        font-weight: 600;
                        color: #333;
                    ">{city}</h3>
                    <p style="
                        margin: 0;
                        font-size: 0.9rem;
                        color: #666;
                    ">📍 {city}, UK</p>
                </div>
            </div>
            
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            ">
                <div style="
                    background: {badge_color};
                    color: white;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-weight: 600;
                    font-size: 1.1rem;
                ">
                    AQI {aqi}
                </div>
                <div style="
                    color: {text_color};
                    font-weight: 500;
                    font-size: 0.9rem;
                ">
                    {aqi_status[0]}
                </div>
            </div>
            
            <div style="
                display: flex;
                justify-content: space-between;
                font-size: 0.9rem;
                color: #666;
            ">
                <div>
                    <span style="font-weight: 500;">🌡️ Temp:</span> {temp}°C
                </div>
                <div>
                    <span style="font-weight: 500;">💧 Hum:</span> {humidity}%
                </div>
            </div>
        </div>
        """
    
    cards_html += """
        </div>
    </div>
    """
    
    return cards_html

def create_polluted_cities_ranking():
    """Create most polluted cities ranking table similar to aqi.in"""
    # Load data for all cities
    df = load_latest_data()
    
    # Calculate AQI for each city and sort by AQI (highest first)
    city_rankings = []
    for _, row in df.iterrows():
        aqi = calc_aqi(row['pm25'])
        aqi_status = get_aqi_status(aqi)
        
        # Calculate how many times above standard (assuming standard is 50)
        standard_multiplier = max(1, int(aqi / 50))
        
        city_rankings.append({
            'city': row['site'],
            'aqi': aqi,
            'status': aqi_status[0],
            'color': aqi_status[2],
            'bg_color': aqi_status[3],
            'standard_multiplier': standard_multiplier
        })
    
    # Sort by AQI (highest first) and take top 10
    city_rankings.sort(key=lambda x: x['aqi'], reverse=True)
    top_10 = city_rankings[:10]
    
    ranking_html = """
    <div style="
        background: white;
        border-radius: 15px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    ">
        <h2 style="
            color: #333;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 10px;
            text-align: center;
        ">Most Polluted Cities 2025</h2>
        <p style="
            color: #666;
            font-size: 1rem;
            text-align: center;
            margin-bottom: 30px;
        ">Real-time most air polluted cities in the country</p>
        
        <!-- Ranking Table -->
        <div style="
            background: #f8f9fa;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        ">
            <table style="
                width: 100%;
                border-collapse: collapse;
                font-size: 0.95rem;
            ">
                <thead>
                    <tr style="
                        background: #4CAF50;
                        color: white;
                        font-weight: 600;
                    ">
                        <th style="padding: 15px; text-align: left; width: 60px;">Rank</th>
                        <th style="padding: 15px; text-align: left;">City</th>
                        <th style="padding: 15px; text-align: center; width: 120px;">AQI</th>
                        <th style="padding: 15px; text-align: center; width: 150px;">AQI Status</th>
                        <th style="padding: 15px; text-align: center; width: 140px;">Standard Value</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for i, city_data in enumerate(top_10, 1):
        # Create a simple bar for AQI visualization
        bar_width = min(100, (city_data['aqi'] / 100) * 100)
        
        # Use darker colors for better visibility
        if city_data['color'] == '#ffff00':  # Yellow
            display_color = '#FF8C00'  # Dark orange for better visibility
        else:
            display_color = city_data['color']
        
        ranking_html += f"""
                    <tr style="
                        background: white;
                        border-bottom: 1px solid #e0e0e0;
                    ">
                        <td style="
                            padding: 15px;
                            font-weight: 600;
                            color: #333;
                        ">{i}</td>
                        <td style="
                            padding: 15px;
                            font-weight: 500;
                            color: #333;
                        ">{city_data['city']}, United Kingdom</td>
                        <td style="
                            padding: 15px;
                            text-align: center;
                        ">
                            <div style="
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                gap: 8px;
                            ">
                                <span style="
                                    font-weight: 600;
                                    color: {display_color};
                                ">{city_data['aqi']}</span>
                                <div style="
                                    width: 40px;
                                    height: 6px;
                                    background: #e0e0e0;
                                    border-radius: 3px;
                                    overflow: hidden;
                                ">
                                    <div style="
                                        width: {bar_width}%;
                                        height: 100%;
                                        background: {display_color};
                                        border-radius: 3px;
                                    "></div>
                                </div>
                            </div>
                        </td>
                        <td style="
                            padding: 15px;
                            text-align: center;
                            color: {display_color};
                            font-weight: 500;
                        ">{city_data['status']}</td>
                        <td style="
                            padding: 15px;
                            text-align: center;
                            color: #666;
                            font-size: 0.9rem;
                        ">{city_data['standard_multiplier']}x above Standard</td>
                    </tr>
        """
    
    ranking_html += """
                </tbody>
            </table>
        </div>
        
        <!-- Footer -->
        <div style="
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        ">
            <span style="
                color: #666;
                font-size: 0.9rem;
            ">Last Updated: 07 Aug 2025, 05:26 PM</span>
        </div>
    </div>
    """
    
    return ranking_html

# Create city cards component
city_cards = pn.pane.HTML(create_city_cards())

# Create polluted cities ranking component
polluted_ranking = pn.pane.HTML(create_polluted_cities_ranking())

# Main dashboard layout - properly centered
main_dashboard = pn.Column(
    header,
    map_pane,
    pn.Column(aqi_card, align='center', width=800),
    charts_row,
    aqi_index,
    city_cards,
    polluted_ranking,
    align='center',
    sizing_mode='stretch_width'
)

# Initialize dynamic content with main dashboard
dynamic_content.append(main_dashboard)

# --- URL PARAMETER HANDLING ---
def get_url_params():
    """Get URL parameters for pollutant and city selection"""
    # For now, return None to always show main dashboard
    # The pollutant detail views will be handled by JavaScript navigation
    return None, None

def create_main_dashboard():
    """Create the main dashboard view"""
    return pn.Column(
        header,
        map_pane,
        pn.Column(aqi_card, align='center', width=800),
        charts_row,
        aqi_index,
        city_cards,
        polluted_ranking,
        align='center',
        sizing_mode='stretch_width'
    )

def create_pollutant_detail_dashboard(pollutant, city):
    """Create the pollutant detail dashboard view"""
    detail_view = pn.pane.HTML(create_detailed_pollutant_view(city, pollutant))
    return pn.Column(
        detail_view,
        align='center',
        sizing_mode='stretch_width'
    )

# Always show main dashboard by default
# Pollutant detail views will be handled by JavaScript navigation
dashboard = create_main_dashboard()

# --- INTERACTIVITY ---
@pn.depends(city_selector.param.value, watch=True)
def update_map(city):
    """Update map when city changes"""
    map_pane.object = create_map(city)

@pn.depends(city_selector.param.value, watch=True)
def update_aqi_card(city):
    """Update AQI card when city changes"""
    aqi_card.object = create_aqi_card(city)

@pn.depends(city_selector.param.value, watch=True)
def update_pollutant_cards(city):
    """Update pollutant cards when city changes"""
    pollutant_cards.object = create_pollutant_cards(city)

@pn.depends(city_selector.param.value, watch=True)
def update_aqi_graph(city):
    """Update AQI graph when city changes"""
    aqi_graph.object = create_historical_aqi_graph(city)

@pn.depends(city_selector.param.value, watch=True)
def update_graph_header(city):
    """Update graph header when city changes"""
    graph_header.object = create_graph_header(city)

# --- RUN DASHBOARD ---
# Make dashboard servable
dashboard.servable()

if __name__ == '__main__':
    dashboard.show()
else:
    # For running in notebook or other environments
    dashboard 