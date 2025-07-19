(function() {
    console.log("CyberLaw Agent Content Script Injected!");

    // Helper to get element's text content or empty string
    function getTextContent(selector, parent = document) {
        const el = parent.querySelector(selector);
        return el ? el.innerText.trim() : '';
    }

    // Function to inject the 'Report Post' button
    function injectReportButton(postElement) {
        // Avoid injecting multiple buttons on the same post
        if (postElement.querySelector('.cyberlaw-report-button')) {
            return;
        }

        const button = document.createElement('button');
        button.className = 'cyberlaw-report-button'; // Use a specific class for styling
        button.textContent = '🚩 Report Post'; // Flag emoji for visual appeal
        button.style.cssText = `
            background-color: #ef4444; /* Red color for flagging */
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            margin-left: 10px;
            opacity: 0.8;
            transition: opacity 0.2s ease-in-out;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        `;
        button.onmouseover = () => button.style.opacity = '1';
        button.onmouseout = () => button.style.opacity = '0.8';

        button.onclick = (event) => {
            event.stopPropagation(); // Prevent clicks from interacting with the original post
            event.preventDefault();

            console.log("Report button clicked!");
            const postContent = extractPostContent(postElement);
            const sourceUrl = window.location.href; // Get the current URL of the page

            if (postContent) {
                // Send message to the extension's popup or background script
                chrome.runtime.sendMessage({
                    type: "REPORT_POST",
                    payload: {
                        postContent: postContent,
                        sourceUrl: sourceUrl,
                        timestamp: new Date().toISOString()
                    }
                }, (response) => {
                    if (response && response.status === 'success') {
                        console.log('Post reported successfully!');
                        button.textContent = '✅ Reported!';
                        button.style.backgroundColor = '#22c55e'; // Green for success
                        button.disabled = true;
                    } else {
                        console.error('Failed to report post:', response ? response.error : 'No response');
                        // Use a custom message box or simple alert for user feedback
                        // For a real extension, you'd use a more sophisticated UI for alerts.
                        alert('Failed to report post. Please try again or open the extension popup directly.');
                    }
                });
            } else {
                alert("Could not extract post content. Please ensure the post is fully loaded and try again.");
            }
        };

        // --- PLATFORM-SPECIFIC INJECTION LOGIC ---
        // This example targets common Twitter/X structures. You will need to inspect
        // the actual DOM of Twitter/X or Facebook or other platforms carefully
        // using browser developer tools (F12) to find reliable selectors.

        let injected = false;

        const actionsBar = postElement.querySelector('[role="group"][aria-label="Tweet actions"], div[data-testid="socialContext"], div[role="group"][aria-label="More actions"]');
        if (actionsBar) {
            // Find existing action buttons to place yours next to them
            const existingActionButtons = actionsBar.querySelectorAll('div[role="button"], a[role="link"]');
            if (existingActionButtons.length > 0) {
                existingActionButtons[existingActionButtons.length - 1].after(button);
                injected = true;
            } else {
                // If no specific buttons, just append to the action bar
                actionsBar.appendChild(button);
                injected = true;
            }
        }

        // Attempt 2: If no action bar found, try to append to the post's text container itself
        // This is less ideal but can work if actionsBar is elusive
        if (!injected) {
            const postTextContainer = postElement.querySelector('[data-testid="tweetText"], div[dir="auto"] > span'); // More general text selector
            if (postTextContainer) {
                // Create a small div to ensure the button is block-level if text is inline
                const wrapper = document.createElement('div');
                wrapper.style.cssText = 'display: flex; justify-content: flex-end; padding-top: 5px;';
                wrapper.appendChild(button);
                postTextContainer.after(wrapper); // Insert after the text container
                injected = true;
            }
        }

        // Add a general class to the post element itself to mark it as processed
        if (injected) {
            postElement.classList.add('cyberlaw-processed-post');
        } else {
            console.warn("CyberLaw Agent: Could not find a suitable injection point for a post.");
        }
    }

    // Function to extract the actual text content of a post
    function extractPostContent(postElement) {
        // This is HIGHLY dependent on the social media platform's DOM structure.
        // For X/Twitter, tweet text is often in specific data-testid or class names.
        // Inspect the page using browser developer tools (F12) to find the correct selectors.
        // Try multiple selectors as fallback if one fails.

        // Common selectors for Twitter/X post text:
        let textContent = getTextContent('[data-testid="tweetText"]', postElement);
        if (!textContent) {
            textContent = getTextContent('div[lang] > span', postElement); // More generic text span
        }
        if (!textContent) {
            textContent = getTextContent('div[dir="auto"] > span', postElement); // Another generic approach
        }
        // Add more selectors if needed for different post types or platforms (e.g., image captions, quotes)

        return textContent || null;
    }

    // Main observer function to find posts and inject buttons
    function observeAndInject() {
        // For X/Twitter, posts are often within <article> tags with data-testid="tweet"
        const postSelector = 'article[data-testid="tweet"]'; // Primary selector for individual tweets/posts

        // Find existing posts on initial load
        document.querySelectorAll(postSelector).forEach((postElement) => {
            if (!postElement.classList.contains('cyberlaw-processed-post')) {
                injectReportButton(postElement);
            }
        });

        // Use MutationObserver to detect dynamically loaded posts (e.g., infinite scroll)
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) { // Only process element nodes
                            // Check if the added node is a post itself or contains posts
                            if (node.matches(postSelector) && !node.classList.contains('cyberlaw-processed-post')) {
                                injectReportButton(node);
                            }
                            node.querySelectorAll(postSelector).forEach((postElement) => {
                                if (!postElement.classList.contains('cyberlaw-processed-post')) {
                                    injectReportButton(postElement);
                                }
                            });
                        }
                    });
                }
            });
        });

        // Observe the body for changes
        observer.observe(document.body, { childList: true, subtree: true });
    }

    // Run the observer logic when the document is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', observeAndInject);
    } else {
        observeAndInject();
    }
})();
