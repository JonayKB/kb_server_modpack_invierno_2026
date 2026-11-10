LootJS.modifiers((event) => {
    event
        .addEntityLootModifier("minecraft:wither")
        .randomChance(1.0)
        .addLoot("goety_revelation:quietus_star");
});