LootJS.modifiers((event) => {
    event
        .addEntityLootModifier("minecraft:warden")
        .randomChance(0.10)
        .addLoot("endrem:black_eye_eye");
});