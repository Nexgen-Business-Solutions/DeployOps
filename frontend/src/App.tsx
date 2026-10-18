import { useState } from 'react'
import reactLogo from './assets/react.svg'
import './App.css'
import { FrappeProvider } from 'frappe-react-sdk'
function App() {
    const [count, setCount] = useState(0)

    return (
        <div className="App">
            <FrappeProvider>
                <h1>Cashmatic Pre-installation checklist</h1>
            </FrappeProvider>
        </div>
    )
}

export default App
