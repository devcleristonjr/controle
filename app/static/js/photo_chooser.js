(function () {
  function setupPhotoChooser(root) {
    const fileInput = root.querySelector('input[type="file"][name="foto"]');
    const cameraInput = root.querySelector('[data-photo-camera-input]');
    const cameraButton = root.querySelector('[data-photo-camera]');
    const galleryButton = root.querySelector('[data-photo-gallery]');
    const nameElement = root.querySelector('[data-photo-name]');

    if (!fileInput || !cameraInput || !cameraButton || !galleryButton) return;

    function updateName(file) {
      if (!nameElement) return;
      nameElement.textContent = file
        ? 'Foto selecionada: ' + file.name
        : 'Nenhuma foto selecionada.';
      nameElement.classList.toggle('text-success', Boolean(file));
    }

    galleryButton.addEventListener('click', function () {
      fileInput.removeAttribute('capture');
      fileInput.click();
    });

    cameraButton.addEventListener('click', function () {
      cameraInput.value = '';
      cameraInput.click();
    });

    fileInput.addEventListener('change', function () {
      updateName(fileInput.files && fileInput.files[0]);
    });

    cameraInput.addEventListener('change', function () {
      const file = cameraInput.files && cameraInput.files[0];
      if (!file) return;

      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        updateName(file);
      } catch (error) {
        console.warn('Não foi possível transferir a foto da câmera:', error);
        fileInput.click();
      }
    });
  }

  document.querySelectorAll('[data-photo-chooser]').forEach(setupPhotoChooser);
})();