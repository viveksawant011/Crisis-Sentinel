
import './App.css';
import MetricCard from './components/metricCard'; './components/MetricCard';
import data from'./mock/mockData.json';
function App() {


  return (
    <>
      <div>
        <h1>CrisisSentinel</h1>
        <p>Supply chain crisis dashboard</p>
      </div>
      <div class="dataSection">
        <MetricCard label="At Risk" value="€4.72M" />
        <MetricCard label="Open Orders" value={data.exposure.open_pos_count} />
        <MetricCard label="Runway (days)" value={data.exposure.total_exposure_eur} />
      </div>
    </>
  )
}

export default App
