
import './App.css';
import mockdata from'./mock/scan.json';
import Header from './components/Header';

function App() {

   console.log(mockdata);
  return (
    
    <>
    
      <div className="page">
        <Header/>
      </div>
     
    </>
  )
}

export default App
