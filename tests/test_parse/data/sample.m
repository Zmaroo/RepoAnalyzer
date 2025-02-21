function area = circle(r)
    area = pi * r^2;
end

function [area, perimeter] = rectangle(width, height)
    area = width * height;
    perimeter = 2 * (width + height);
end

% Class definition
classdef User
    properties
        name
        age
    end
    
    methods
        function obj = User(name, age)
            obj.name = name;
            obj.age = age;
        end
        
        function result = isAdult(obj)
            result = obj.age >= 18;
        end
    end
end 