from math import floor


def isBalanced(string):
     stack= []
     for string_ in string:
         if string_ in ('(','[','{'):
            stack.append(string_)
         else:  
             if not stack:
                 return False 
             char = stack.pop()
          
             if char == '(':
                 if string_ != ')':
                     return False
             elif char == '[':
                 if string_ != ']':
                     return False
             elif char == '{':
                 if string_ != '}':
                     return False     
     if stack:
          return False
     return True    
    

 
print(isBalanced("(({})[])[["))


def prefix_sum(arr):
    ans = []
    for i in range(len(arr)):
        sub = arr[:i+1]
        max_sub = max(sub)
        
        for idx in range(len(sub)):
            sub[idx] += max_sub
            max_sub = max(max_sub,sub[idx])
        ans.append(sum(sub))
    return ans 


print(prefix_sum([1,2,1]))
print(prefix_sum([5,1,4,2]))


def binary(num):
    a = []
    
    while num > 0:
        a.append(str(num % 2))
        num //= 2
        
    return "".join(a[::-1])

print(binary(3))

