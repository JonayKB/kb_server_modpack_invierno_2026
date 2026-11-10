StartupEvents.registry('item', event => {
    event.create('scroll_of_class_choice')
        .displayName('Scroll of Class Choice')
        .texture('kubejs:item/scroll_of_class_choice') // Define o caminho da textura
        .maxStackSize(1) // Opcional: Define que o item não acumula (pack de 1)
        .glow(true); // Opcional: Dá um brilho de encantamento ao item
})