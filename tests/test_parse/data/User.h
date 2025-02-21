#import <Foundation/Foundation.h>

@interface User : NSObject

@property (nonatomic, strong) NSString *name;
@property (nonatomic, assign) NSInteger age;

- (instancetype)initWithName:(NSString *)name age:(NSInteger)age;
- (BOOL)isAdult;

@end 