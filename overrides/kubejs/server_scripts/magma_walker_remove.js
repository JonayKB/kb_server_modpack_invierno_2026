LootJS.modifiers(event => {
    event
        .addLootTypeModifier(LootType.CHEST)
        .removeLoot('relics:magma_walker')

    event
        .addLootTypeModifier(LootType.ENTITY)
        .removeLoot('relics:magma_walker')

    event
        .addLootTypeModifier(LootType.FISHING)
        .removeLoot('relics:magma_walker')

    event
        .addLootTypeModifier(LootType.GIFT)
        .removeLoot('relics:magma_walker')
})