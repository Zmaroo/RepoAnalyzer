function circle(r)
    return π * r^2
end

area = r -> π * r^2

rectangle(w, h) = w * h

macro twice(ex)
    return :(2 * $ex)
end
