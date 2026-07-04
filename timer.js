function startQuizTimer(seconds, displayId, formId) {
    const display = document.getElementById(displayId);
    const form = document.getElementById(formId);
    let remaining = seconds;

    function updateDisplay() {
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        display.textContent = `⏱ ${m}:${s.toString().padStart(2, '0')}`;
    }

    updateDisplay();
    const interval = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(interval);
            display.textContent = "Time's up! Submitting...";
            form.submit();
        } else {
            updateDisplay();
        }
    }, 1000);
}
