(() => {
  const form = document.getElementById("storyForm");
  const photoInput = document.getElementById("photo");
  const preview = document.getElementById("preview");
  const uploadText = document.getElementById("uploadText");
  const resultCard = document.getElementById("resultCard");
  const submitBtn = document.getElementById("submitBtn");
  const spinner = document.getElementById("spinner");
  const btnText = document.getElementById("btnText");
  const errorBox = document.getElementById("errorBox");

  const showError = (message) => {
    errorBox.textContent = message;
    errorBox.style.display = "block";
  };

  // Image preview
  photoInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (loaded) => {
      preview.src = loaded.target.result;
      preview.style.display = "inline-block";
      uploadText.style.display = "none";
    };
    reader.readAsDataURL(file);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitBtn.disabled = true;
    spinner.style.display = "block";
    btnText.textContent = "Weaving your story...";
    resultCard.style.display = "none";
    errorBox.style.display = "none";

    try {
      const response = await fetch("/generate-vision-story", { method: "POST", body: new FormData(form) });
      let data = {};
      try {
        data = await response.json();
      } catch {
        /* not JSON: handled below */
      }
      if (!response.ok || data.error || !data.story) {
        showError(data.error || "Something went wrong. Please try again.");
        return;
      }
      document.getElementById("storyTitle").textContent = data.title;
      document.getElementById("storyBody").textContent = data.story;
      resultCard.style.display = "block";
      form.style.display = "none"; // hide the form to focus on the story
    } catch (error) {
      console.error("Error:", error);
      showError("Could not reach the server. Please try again.");
    } finally {
      submitBtn.disabled = false;
      spinner.style.display = "none";
      btnText.textContent = "Generate Story";
    }
  });

  document.getElementById("againBtn").addEventListener("click", () => location.reload());
})();
