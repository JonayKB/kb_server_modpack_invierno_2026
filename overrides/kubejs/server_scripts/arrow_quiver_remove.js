LootJS.modifiers(event => {
    event
        .addLootTypeModifier(LootType.CHEST)
        .removeLoot('relics:arrow_quiver')

    event
        .addLootTypeModifier(LootType.ENTITY)
        .removeLoot('relics:arrow_quiver')

    event
        .addLootTypeModifier(LootType.FISHING)
        .removeLoot('relics:arrow_quiver')

    event
        .addLootTypeModifier(LootType.GIFT)
        .removeLoot('relics:arrow_quiver')
})