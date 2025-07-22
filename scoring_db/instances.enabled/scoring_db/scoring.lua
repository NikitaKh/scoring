box.cfg{}

-- Create scoring space --
local scoring = box.schema.space.create('scoring', { if_not_exists = true })

scoring:format({
    { name = 'uid', type = 'string' },
    { name = 'score', type = 'number' }
})

scoring:create_index('uid_idx', { parts = { 'uid' }, if_not_exists = true })

local fiber = require('fiber')

function cache_set(uid, score, ttl)
    box.space.scoring:replace{ uid, score }
    fiber.create(function()
        fiber.sleep(ttl)
        box.space.scoring:delete{ uid }
    end)
    return true
end

function cache_get(uid)
    local tuple = box.space.scoring.index.uid_idx:get{ uid }
    if tuple then
        return tuple[2]
    else
        return nil
    end
end

box.schema.func.create('cache_set', {
    language = 'Lua',
    if_not_exists = true,
    is_deterministic = false,
    is_sandboxed = false
})

box.schema.func.create('cache_get', {
    language = 'Lua',
    if_not_exists = true,
    is_deterministic = false,
    is_sandboxed = false
})


-- Create interests space --
local interests = box.schema.space.create('interests', { if_not_exists = true })

interests:format({
    { name = 'id', type = 'unsigned' },
    { name = 'interest', type = 'array' }
})

interests:create_index('primary', { parts = { 'id' }, if_not_exists = true })

-- local predefined_interests = { "cars", "pets", "travel", "hi-tech", "sport", "music", "books", "tv", "cinema", "geek", "otus" }
local predefined_values = {
    ["1"] = { "sport", "travel" },
    ["2"] = { "pets", "books" },
    ["3"] = { "otus", "pets" },
    ["4"] = { "pets", "travel" }
}

for id, list in pairs(predefined_values) do
    interests:upsert({ tonumber(id), list }, {{'=', 2, list}})
end

function interests_get(id)
    local tuple = box.space.interests:get{ id }
    if tuple then
        return unpack(tuple[2])  -- список интересов
    else
        return {}
    end
end

-- Register function
box.schema.func.create('interests_get', {
    language = 'Lua',
    if_not_exists = true,
    is_deterministic = false,
    is_sandboxed = false
})

