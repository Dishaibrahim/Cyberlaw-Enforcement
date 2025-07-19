chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    console.log("Background script received message:", request);

    if (request.type === "REPORT_POST") {
      
        console.log("Background script acknowledging REPORT_POST. Popup should handle.");
        sendResponse({ status: 'success', message: 'Message received by background.' });
    }

    
    return true;
});

console.log("CyberLaw Agent Background Service Worker Started.");
