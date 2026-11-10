ItemEvents.rightClicked('kubejs:scroll_of_class_choice', event => {
    const { player, item } = event;
    
    // Faz o jogador executar o comando secretamente para abrir a sua GUI
    player.runCommandSilent('/classenhancement');
    
    // IMPORTANTE: Se você quiser que o item seja CONSUMIDO (gasto) ao usar,
    // remova as duas barras '//' do começo da linha abaixo:
    item.count--;
})