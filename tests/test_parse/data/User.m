#import "User.h"

@implementation User

- (instancetype)initWithName:(NSString *)name age:(NSInteger)age {
    self = [super init];
    if (self) {
        _name = name;
        _age = age;
    }
    return self;
}

- (BOOL)isAdult {
    return self.age >= 18;
}

- (NSString *)description {
    return [NSString stringWithFormat:@"%@ (%ld years old)", self.name, (long)self.age];
}

@end 