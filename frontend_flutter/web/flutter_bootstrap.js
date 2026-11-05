{{flutter_js}}
{{flutter_build_config}}

_flutter.loader.load({
  onEntrypointLoaded: async function(engineInitializer) {
    // Εδώ ορίζουμε ρητά τον HTML renderer για να αποφύγουμε τη λευκή οθόνη
    const appRunner = await engineInitializer.initializeEngine({
      renderer: "html"
    });
    await appRunner.runApp();
  }
});