// Feedback Modal Functionality

let selectedRating = 0;
let currentPlaceName = "";
let currentLocation = "";

// Open feedback modal
function openFeedbackModal(placeName, location) {
    selectedRating = 0;
    currentPlaceName = placeName;
    currentLocation = location;
    
    const modal = document.getElementById("feedbackModal");
    document.getElementById("feedbackPlaceName").textContent = placeName;
    document.getElementById("ratingText").textContent = "Select a rating";
    document.getElementById("feedbackMessage").textContent = "";
    
    // Reset all stars
    document.querySelectorAll(".star").forEach(star => {
        star.classList.remove("selected");
        star.style.opacity = "0.4";
    });
    
    // Prevent background scroll
    document.body.style.overflow = "hidden";
    modal.style.display = "flex";
}

// Close feedback modal
function closeFeedbackModal() {
    const modal = document.getElementById("feedbackModal");
    document.body.style.overflow = "auto";
    modal.style.display = "none";
    selectedRating = 0;
}

// Handle star rating clicks
document.querySelectorAll(".star").forEach(star => {
    star.addEventListener("click", function() {
        selectedRating = parseInt(this.getAttribute("data-value"));
        
        // Update visual feedback
        document.querySelectorAll(".star").forEach((s, index) => {
            if (index < selectedRating) {
                s.classList.add("selected");
                s.style.opacity = "1";
            } else {
                s.classList.remove("selected");
                s.style.opacity = "0.4";
            }
        });
        
        // Update text
        const messages = {
            1: "Didn't match my vibe...",
            2: "Could be better",
            3: "It was okay",
            4: "Great place!",
            5: "Perfect vibe! 🎉"
        };
        document.getElementById("ratingText").textContent = messages[selectedRating];
    });
    
    // Hover effect
    star.addEventListener("mouseover", function() {
        const hoverValue = parseInt(this.getAttribute("data-value"));
        document.querySelectorAll(".star").forEach((s, index) => {
            if (index < hoverValue) {
                s.style.opacity = "0.7";
            } else {
                s.style.opacity = "0.3";
            }
        });
    });
});

// Reset hover effect
document.querySelector(".stars").addEventListener("mouseout", function() {
    document.querySelectorAll(".star").forEach((s, index) => {
        if (index < selectedRating) {
            s.style.opacity = "1";
        } else {
            s.style.opacity = "0.4";
        }
    });
});

// Submit feedback
function submitFeedback() {
    if (selectedRating === 0) {
        document.getElementById("feedbackMessage").textContent = "⚠️ Please select a rating";
        document.getElementById("feedbackMessage").style.color = "#ef4444";
        return;
    }
    
    // Get vibe data from sessionStorage
    const vibeData = JSON.parse(sessionStorage.getItem("vibeData") || "{}");
    
    const feedbackData = {
        place_name: currentPlaceName,
        vibe: vibeData.vibe || "unknown",
        user_rating: selectedRating,
        location: vibeData.location || "unknown"
    };
    
    // Show loading state
    const submitBtn = document.querySelector(".btn-feedback-submit");
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Submitting...";
    submitBtn.disabled = true;
    
    // Send feedback to backend
    fetch("/api/feedback", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(feedbackData)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            document.getElementById("feedbackMessage").textContent = "✅ " + data.message;
            document.getElementById("feedbackMessage").style.color = "#10b981";
            
            // Close modal after 2 seconds
            setTimeout(() => {
                closeFeedbackModal();
                // Refresh the places to show updated feedback stats
                location.reload();
            }, 2000);
        } else {
            throw new Error(data.error || "Failed to submit feedback");
        }
    })
    .catch(err => {
        console.error("Feedback error:", err);
        document.getElementById("feedbackMessage").textContent = "❌ " + err.message;
        document.getElementById("feedbackMessage").style.color = "#ef4444";
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    });
}

// Close modal when clicking the X button
document.querySelector(".feedback-close").addEventListener("click", closeFeedbackModal);

// Close modal when clicking outside of it
window.addEventListener("click", function(event) {
    const modal = document.getElementById("feedbackModal");
    if (event.target === modal) {
        closeFeedbackModal();
    }
});
