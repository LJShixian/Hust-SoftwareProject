void Hannuo(int n,int a,int b,int c){
    if(n==1){
        printf("%d->%d\n",a,c);
        return;
    }
    else{
        Hannuo(n-1,a,c,b);
        printf("%d->%d\n",a,c);
        Hannuo(n-1,b,a,c);
    }
}
int main() {
    int n;
    scanf("%d", &n);
    Hannuo(n,1,2,3);
    return 0;
}