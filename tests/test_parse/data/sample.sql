CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INTEGER CHECK (age >= 0)
);

CREATE FUNCTION is_adult(user_age INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN user_age >= 18;
END;
$$ LANGUAGE plpgsql;

SELECT * FROM users WHERE is_adult(age); 