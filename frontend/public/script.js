// frontend/public/script.js


const appId = typeof __app_id !== 'undefined' ? __app_id : 'cyberlaw-app-dev';
let firebaseConfig = {};
try {
    if (typeof __firebase_config !== 'undefined' && __firebase_config) {
        firebaseConfig = JSON.parse(__firebase_config);
        console.log("Firebase Config loaded successfully:", firebaseConfig);
    } else {
        console.warn("Firebase Config (__firebase_config) is undefined or empty. Using default empty config.");
    }
} catch (e) {
    console.error("Error parsing __firebase_config:", e);
    firebaseConfig = {}; 
}
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;


const FASTAPI_BACKEND_URL = 'http://127.0.0.1:8000';

// Firebase instances
let app;
let db;
let auth;
let userId = null;

// Global state for the application (mimicking React's state)
let appState = {
    postContent: '',
    postLink: '',
    victimInfo: '',
    victimEthAddress: '',
    status: 'Idle',
    log: [],
    isProcessing: false,
    cases: [],
    error: '',
    showCourtroom: false,
    currentCaseIdForCourtroom: null,
    courtroomSessionState: {
        court_status: 'IDLE',
        current_turn_agent: null,
        transcript: [],
        jury_deliberation_history: [],
        jury_votes: {},
        final_verdict: null,
        error_message: null,
        agents_status: {}
    }
};

// Agent representation data (static in frontend)
const agentsData = [
    { id: 'prosecution', name: 'Prosecution Lawyer', role: 'Prosecutor', icon: '⚖️' },
    { id: 'defense', name: 'Defense Lawyer', role: 'Defender', icon: '🛡️' },
    { id: 'judge', name: 'Court Judge', role: 'Adjudicator', icon: '👨‍⚖️' },
    { id: 'cyber_expert', name: 'Cyber Law Expert', role: 'Jury', icon: '💻' },
    { id: 'digital_activist', name: 'Digital Rights Activist', role: 'Jury', icon: '✊' },
    { id: 'social_media', name: 'Social Media Expert', role: 'Jury', icon: '📱' },
    { id: 'clerk', name: 'Court Clerk', role: 'Recorder', icon: '📜'}
];

let courtroomPollingInterval = null; // To store the interval ID for polling

// --- DOM Element References ---
const postContentInput = document.getElementById('postContent');
const postLinkInput = document.getElementById('postLink');
const victimInfoInput = document.getElementById('victimInfo');
const victimEthAddressInput = document.getElementById('victimEthAddress');
const flagPostButton = document.getElementById('flag-post-button');
const buttonTextSpan = document.getElementById('button-text');
const buttonSpinnerSpan = document.getElementById('button-spinner');
const logDisplay = document.getElementById('log-display');
const currentStatusSpan = document.getElementById('current-status');
const userIdDisplay = document.getElementById('user-id-display');
const casesTableBody = document.getElementById('cases-table-body');
const errorDisplay = document.getElementById('error-display');
const errorMessageSpan = document.getElementById('error-message');

// Courtroom specific DOM elements
const mainContentArea = document.getElementById('main-content');
const courtroomSessionArea = document.getElementById('courtroom-session-area');
const courtroomCaseIdDisplay = document.getElementById('courtroom-case-id');
const startCourtroomButton = document.getElementById('start-courtroom-button');
const resetCourtroomButton = document.getElementById('reset-courtroom-button');
const courtroomCurrentPhaseDisplay = document.getElementById('courtroom-current-phase');
const agentPanelsContainer = document.getElementById('agent-panels');
const courtroomTranscriptContent = document.getElementById('courtroom-transcript-content');
const courtroomTranscriptScrollArea = document.getElementById('courtroom-transcript');
const finalVerdictDisplay = document.getElementById('final-verdict-display');

// Verdict details elements
const verdictDecision = document.getElementById('verdict-decision');
const verdictFine = document.getElementById('verdict-fine');
const verdictBan = document.getElementById('verdict-ban');
const verdictExplanation = document.getElementById('verdict-explanation');
const verdictCompensation = document.getElementById('verdict-compensation');
const verdictSocialScore = document.getElementById('verdict-social-score');
const verdictSocialScoreExplanation = document.getElementById('verdict-social-score-explanation');


// --- Utility Functions ---

function addLog(message) {
    appState.log.push(`${new Date().toLocaleTimeString()}: ${message}`);
    renderLog();
}

function setError(message) {
    appState.error = message;
    renderError();
}

function setStatus(message) {
    appState.status = message;
    renderStatus();
}

function updateProcessingState(isProcessing) {
    appState.isProcessing = isProcessing;
    flagPostButton.disabled = isProcessing;
    if (isProcessing) {
        flagPostButton.classList.add('processing');
        buttonTextSpan.classList.add('hidden');
        buttonSpinnerSpan.classList.remove('hidden');
    } else {
        flagPostButton.classList.remove('processing');
        buttonTextSpan.classList.remove('hidden');
        buttonSpinnerSpan.classList.add('hidden');
    }
}

// --- Render Functions (to update UI based on appState) ---

function renderLog() {
    logDisplay.innerHTML = ''; // Clear previous logs
    if (appState.log.length === 0) {
        logDisplay.innerHTML = '<p class="text-gray-500 italic">No activity yet. Flag a post to start.</p>';
    } else {
        appState.log.forEach(entry => {
            const p = document.createElement('p');
            p.className = 'mb-1';
            p.textContent = entry;
            logDisplay.appendChild(p);
        });
    }
    logDisplay.scrollTop = logDisplay.scrollHeight; // Auto-scroll
}

function renderError() {
    if (appState.error) {
        errorDisplay.classList.remove('hidden');
        errorMessageSpan.textContent = appState.error;
    } else {
        errorDisplay.classList.add('hidden');
        errorMessageSpan.textContent = '';
    }
}

function renderStatus() {
    currentStatusSpan.textContent = appState.status;
}

function renderUserId() {
    userIdDisplay.textContent = userId || 'Loading...';
}

function renderCasesTable() {
    casesTableBody.innerHTML = ''; // Clear existing rows
    if (appState.cases.length === 0) {
        casesTableBody.innerHTML = '<tr><td colspan="8" class="py-3 px-4 text-sm text-gray-500 italic text-center">No cases recorded on the ledger yet.</td></tr>';
    } else {
        appState.cases.forEach(_case => {
            const row = document.createElement('tr');
            row.className = 'border-b border-gray-200 hover:bg-gray-50';
            row.innerHTML = `
                <td class="py-3 px-4 text-sm text-gray-800 font-mono break-all">${_case.id ? _case.id.substring(0, 10) + '...' : 'N/A'}</td>
                <td class="py-3 px-4 text-sm text-gray-800">${_case.timestamp ? new Date(_case.timestamp).toLocaleString() : 'N/A'}</td>
                <td class="py-3 px-4 text-sm text-gray-800">${_case.courtroomStatus || _case.status || 'N/A'}</td>
                <td class="py-3 px-4 text-sm text-gray-800">${_case.analysis?.violationType || 'N/A'}</td>
                <td class="py-3 px-4 text-sm text-gray-800">${_case.courtroomVerdict?.verdict_type || 'N/A'}</td>
                <td class="py-3 px-4 text-sm text-gray-800">
                    ${_case.finalFineWei ? `${(_case.finalFineWei / (10**18)).toFixed(4)}` : 'N/A'}
                </td>
                <td class="py-3 px-4 text-sm text-gray-800">
                    ${_case.finalCompensationWei ? `${(_case.finalCompensationWei / (10**18)).toFixed(4)}` : 'N/A'}
                </td>
                <td class="py-3 px-4 text-sm text-gray-800">${_case.socialScore || 'N/A'}</td>
            `;
            casesTableBody.appendChild(row);
        });
    }
}

function renderAppUI() {
    if (appState.showCourtroom) {
        mainContentArea.classList.add('hidden');
        courtroomSessionArea.classList.remove('hidden');
        courtroomCaseIdDisplay.textContent = appState.currentCaseIdForCourtroom;
        renderCourtroomSessionState(); // Initial render for courtroom
    } else {
        mainContentArea.classList.remove('hidden');
        courtroomSessionArea.classList.add('hidden');
    }
}

function renderCourtroomSessionState() {
    const state = appState.courtroomSessionState;

    // Update current phase
    courtroomCurrentPhaseDisplay.textContent = state.court_status.replace(/_/g, ' ');

    // Update agent panels
    agentPanelsContainer.innerHTML = '';
    agentsData.forEach(agent => {
        const agentDiv = document.createElement('div');
        agentDiv.className = `bg-gray-50 p-3 rounded-lg shadow-md flex flex-col items-center text-center transition-all duration-300
            ${state.current_turn_agent === agent.name ? 'border-2 border-indigo-500 scale-105' : 'border border-gray-200'}`;
        agentDiv.innerHTML = `
            <div class="text-3xl mb-1">${agent.icon}</div>
            <h4 class="font-bold text-base text-indigo-800">${agent.name}</h4>
            <p class="text-xs text-gray-600">${agent.role}</p>
            <p class="text-xs mt-1 font-medium ${state.current_turn_agent === agent.name ? 'text-indigo-600' : 'text-gray-500'}">
                Status: ${state.agents_status[agent.name] || "Waiting"}
            </p>
        `;
        agentPanelsContainer.appendChild(agentDiv);
    });

    // Update courtroom transcript
    courtroomTranscriptContent.innerHTML = '';
    if (state.transcript.length === 0) {
        courtroomTranscriptContent.innerHTML = '<p class="text-gray-500 italic">Session transcript will appear here...</p>';
    } else {
        state.transcript.forEach((line, index) => {
            const p = document.createElement('p');
            let className = 'mb-1 text-sm';
            if (line.type === 'statement' || line.type === 'vote' || line.type === 'query' || line.type === 'answer') {
                className += ' font-medium text-gray-800';
            } else if (line.type === 'system') {
                className += ' italic text-indigo-700';
            } else if (line.type === 'error') {
                className += ' text-red-600 font-semibold';
            } else {
                className += ' text-gray-600';
            }
            p.className = className;
            p.innerHTML = `<span class="font-semibold">${line.agent_name || line.agentName}:</span> ${line.message} <span class="text-xs text-gray-400 ml-2">${new Date(line.timestamp * 1000).toLocaleTimeString()}</span>`;
            courtroomTranscriptContent.appendChild(p);
        });
    }
    courtroomTranscriptScrollArea.scrollTop = courtroomTranscriptScrollArea.scrollHeight; // Auto-scroll

    // Update final verdict display
    if (state.final_verdict) {
        finalVerdictDisplay.classList.remove('hidden');
        verdictDecision.textContent = state.final_verdict.verdict_type;
        verdictFine.textContent = state.final_verdict.final_fine_eth ? `${state.final_verdict.final_fine_eth.toFixed(4)} ETH/MATIC` : '0 ETH/MATIC';
        verdictBan.textContent = state.final_verdict.final_ban_status;
        verdictExplanation.textContent = state.final_verdict.explanation;
        verdictCompensation.textContent = state.final_verdict.final_compensation_eth ? `${state.final_verdict.final_compensation_eth.toFixed(4)} ETH/MATIC` : '0 ETH/MATIC';
        verdictSocialScore.textContent = state.final_verdict.social_score;
        verdictSocialScoreExplanation.textContent = `(${state.final_verdict.social_score_explanation})`;

        // Hide start button, show reset button
        startCourtroomButton.classList.add('hidden');
        resetCourtroomButton.classList.remove('hidden');
    } else {
        finalVerdictDisplay.classList.add('hidden');
        // Show start button, hide reset button if not yet started
        if (state.court_status === 'IDLE') {
            startCourtroomButton.classList.remove('hidden');
            resetCourtroomButton.classList.add('hidden');
        }
    }

    // Handle button visibility based on courtroom status
    if (state.court_status === 'COMPLETED' || state.court_status === 'ERROR') {
        startCourtroomButton.classList.add('hidden');
        resetCourtroomButton.classList.remove('hidden');
        clearInterval(courtroomPollingInterval); // Stop polling
        courtroomPollingInterval = null;
    } else if (state.court_status === 'IDLE') {
        startCourtroomButton.classList.remove('hidden');
        resetCourtroomButton.classList.add('hidden');
    } else { // Session is in progress
        startCourtroomButton.classList.add('hidden');
        resetCourtroomButton.classList.add('hidden');
    }

    // If courtroom is active and not completed/error, ensure polling is active
    if (appState.showCourtroom && (state.court_status !== 'COMPLETED' && state.court_status !== 'ERROR') && courtroomPollingInterval === null) {
        startCourtroomPolling();
    }
}

// --- Firebase Initialization and Listeners ---

async function initializeFirebase() {
    try {
        if (!app) { // Only initialize if not already initialized
            app = firebase.initializeApp(firebaseConfig);
            db = firebase.firestore(app);
            auth = firebase.auth(app);
            console.log("Firebase App, Firestore, and Auth initialized successfully.");
        }

        const unsubscribeAuth = firebase.auth().onAuthStateChanged(auth, async (user) => {
            if (user) {
                userId = user.uid;
                addLog(`User authenticated: ${userId}`);
                console.log("User authenticated:", userId);
                renderUserId();
                setupFirestoreSnapshotListener(); // Setup Firestore listener after auth
            } else {
                console.log("No user authenticated. Attempting sign-in.");
                try {
                    if (initialAuthToken) {
                        await firebase.auth().signInWithCustomToken(auth, initialAuthToken);
                        console.log("Signed in with custom token.");
                    } else {
                        await firebase.auth().signInAnonymously(auth);
                        console.log("Signed in anonymously.");
                    }
                } catch (e) {
                    setError(`Firebase Auth Sign-in Error: ${e.message}`);
                    addLog(`Firebase Auth Sign-in Error: ${e.message}`);
                    console.error("Firebase Auth Sign-in Error:", e);
                }
            }
        });
        // Return unsubscribe function if needed for cleanup, though for extensions it often runs for lifetime
        // return () => unsubscribeAuth();
    } catch (e) {
        console.error("Error initializing Firebase services:", e);
        setError(`Firebase initialization failed: ${e.message}`);
    }
}

function setupFirestoreSnapshotListener() {
    if (!userId || !db) {
        console.warn("Cannot set up Firestore listener: userId or db not available.");
        return;
    }

    console.log("Setting up Firestore snapshot listener for public cases.");
    const publicCasesCollectionRef = db.collection(`artifacts/${appId}/public/data/cyberlawCases`);
    const q = publicCasesCollectionRef; // No complex queries needed for now

    // onSnapshot returns an unsubscribe function
    const unsubscribe = q.onSnapshot(snapshot => {
        if (!userId) { // Double check userId in snapshot callback too
            console.warn("userId not available during Firestore snapshot processing in callback.");
            return;
        }
        const fetchedCases = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));
        appState.cases = fetchedCases;
        addLog(`Updated public ledger with ${fetchedCases.length} cases.`);
        console.log("Firestore snapshot updated:", fetchedCases.length, "cases.");
        renderCasesTable(); // Re-render the table
    }, error => {
        setError(`Firestore Snapshot Error: ${error.message}`);
        addLog(`Firestore Snapshot Error: ${error.message}`);
        console.error("Firestore Snapshot Error:", error);
    });

    // In a full application, you'd manage this unsubscribe, but for a simple extension
    // it might run for the lifetime of the popup.
    // To clean up: unsubscribe();
}


// --- Backend API Interaction Functions ---

async function handleFlagPost() {
    // Input validation
    const postContent = postContentInput.value.trim();
    const postLink = postLinkInput.value.trim();
    const victimInfo = victimInfoInput.value.trim();
    const victimEthAddress = victimEthAddressInput.value.trim();

    if (!postContent) { setError('Please enter the post content.'); return; }
    if (!victimInfo) { setError('Please enter victim information.'); return; }
    if (victimEthAddress && !/^0x[a-fA-F0-9]{40}$/.test(victimEthAddress)) {
         setError('Please enter a valid Ethereum/Polygon address (starts with 0x and is 42 characters long).'); return;
    }
    if (!userId) { setError('Authentication not ready. Please wait a moment or refresh.'); return; }
    if (!FASTAPI_BACKEND_URL) { setError('Backend URL is not defined.'); return; }

    updateProcessingState(true);
    appState.log = []; // Clear log for new process
    setError('');
    setStatus('Initiating initial analysis via FastAPI backend...');
    addLog("Sending flag post request to backend...");

    try {
        const response = await fetch(`${FASTAPI_BACKEND_URL}/flag_post`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                postContent,
                victimInfo,
                userId,
                postLink,
                victimEthAddress,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `Backend responded with status ${response.status}: ${JSON.stringify(data)}`);
        }

        addLog(`Initial Analysis Backend Response: ${JSON.stringify(data)}`);
        setStatus(data.message || 'Initial analysis complete.');
        console.log("Backend response received:", data);

        if (data.case_details && data.case_details.status !== 'Case Closed - No Violation') {
            appState.currentCaseIdForCourtroom = data.case_id;
            appState.showCourtroom = true; // Show the courtroom session component
            setStatus('Violation detected. Courtroom session commencing!');
            addLog("Violation detected, showing courtroom for case: " + data.case_id);
            renderAppUI(); // Switch UI to courtroom
        } else {
             setStatus('No violation detected. Case closed.');
             addLog("No violation detected. Case closed.");
        }

    } catch (err) {
        setError(`Error during initial processing: ${err.message}`);
        addLog(`Error during initial processing: ${err.message}`);
        setStatus('Error during initial processing.');
        console.error("Error in handleFlagPost:", err);
    } finally {
        updateProcessingState(false);
        // Clear form fields after submission
        postContentInput.value = '';
        postLinkInput.value = '';
        victimInfoInput.value = '';
        // victimEthAddressInput.value = ''; // You might choose to keep this if user frequently uses same address
    }
}

async function startCourtroomSession() {
    const caseId = appState.currentCaseIdForCourtroom;
    if (!caseId) {
        setError("No case selected to start courtroom session.");
        return;
    }

    setStatus('Starting courtroom session...');
    addLog(`Requesting backend to start courtroom for Case ID: ${caseId}`);
    startCourtroomButton.disabled = true; // Disable button to prevent multiple clicks

    try {
        const response = await fetch(`${FASTAPI_BACKEND_URL}/start_courtroom_session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: caseId })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to start courtroom session on backend.");
        }
        addLog(`Backend response: ${data.message}`);
        setStatus('Courtroom session initialized on backend. Awaiting updates...');
        appState.courtroomSessionState.court_status = 'STARTING'; // Set initial status for UI
        renderCourtroomSessionState();
        startCourtroomPolling(); // Start polling for updates
    } catch (err) {
        setError("Error starting courtroom session: " + err.message);
        addLog("Error starting courtroom session: " + err.message);
        appState.courtroomSessionState.court_status = 'ERROR';
        appState.courtroomSessionState.error_message = err.message;
        renderCourtroomSessionState();
    } finally {
        startCourtroomButton.disabled = false; // Re-enable if needed, or keep disabled if session truly starts
    }
}

async function fetchCourtroomUpdates() {
    const caseId = appState.currentCaseIdForCourtroom;
    if (!caseId) return;

    try {
        const response = await fetch(`${FASTAPI_BACKEND_URL}/get_courtroom_updates?case_id=${caseId}`);
        const data = await response.json();

        if (response.ok) {
            appState.courtroomSessionState = data;
            renderCourtroomSessionState();

            if (data.court_status === 'COMPLETED' || data.court_status === 'ERROR') {
                clearInterval(courtroomPollingInterval);
                courtroomPollingInterval = null;
                addLog(`Courtroom session for ${caseId} ended with status: ${data.court_status}`);
                setStatus(`Courtroom session concluded: ${data.court_status}`);
                // No need to call onSessionEnd as it's a direct UI render now
            }
        } else {
            setError(data.detail || "Failed to fetch courtroom updates.");
            addLog("Failed to fetch courtroom updates: " + (data.detail || "Unknown error"));
            clearInterval(courtroomPollingInterval);
            courtroomPollingInterval = null;
            appState.courtroomSessionState.court_status = 'ERROR';
            appState.courtroomSessionState.error_message = data.detail || "Failed to fetch updates.";
            renderCourtroomSessionState();
        }
    } catch (err) {
        setError("Network error fetching courtroom updates: " + err.message);
        addLog("Network error fetching courtroom updates: " + err.message);
        clearInterval(courtroomPollingInterval);
        courtroomPollingInterval = null;
        appState.courtroomSessionState.court_status = 'ERROR';
        appState.courtroomSessionState.error_message = err.message;
        renderCourtroomSessionState();
    }
}

function startCourtroomPolling() {
    if (courtroomPollingInterval) {
        clearInterval(courtroomPollingInterval);
    }
    courtroomPollingInterval = setInterval(fetchCourtroomUpdates, 3000); // Poll every 3 seconds
    addLog("Started polling for courtroom updates.");
}

function resetCourtroomSessionView() {
    clearInterval(courtroomPollingInterval);
    courtroomPollingInterval = null;
    appState.showCourtroom = false;
    appState.currentCaseIdForCourtroom = null;
    appState.courtroomSessionState = {
        court_status: 'IDLE',
        current_turn_agent: null,
        transcript: [],
        jury_deliberation_history: [],
        jury_votes: {},
        final_verdict: null,
        error_message: null,
        agents_status: {}
    };
    setError(null); // Clear any errors
    setStatus('Idle'); // Reset main app status
    renderAppUI(); // Switch back to main flagging UI
    renderCourtroomSessionState(); // Reset courtroom UI elements
    addLog("Courtroom session view reset.");
}

// --- Web Extension Specifics ---

// Listener for messages from content-script.js
if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage) {
    console.log("Setting up chrome.runtime.onMessage listener for content script messages.");
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === "REPORT_POST") {
            console.log("Received REPORT_POST from content script:", request.payload);
            postContentInput.value = request.payload.postContent || '';
            postLinkInput.value = request.payload.sourceUrl || '';
            addLog(`Received flagged post content from ${request.payload.sourceUrl}`);
            sendResponse({ status: 'success', message: 'Post data received by popup.' });
        }
    });
} else {
    console.warn("Chrome Runtime API not available. This app is designed as a browser extension.");
}


window.onload = async () => {
    console.log("Window loaded. Initializing application.");
    
    await initializeFirebase();

    
    flagPostButton.addEventListener('click', handleFlagPost);
    startCourtroomButton.addEventListener('click', startCourtroomSession);
    resetCourtroomButton.addEventListener('click', resetCourtroomSessionView);

    
    renderError();
    renderStatus();
    renderLog();
    renderUserId();
    renderCasesTable();
    renderAppUI(); 
};
