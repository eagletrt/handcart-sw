/*
    Program to charge the pig in the handcart
    E-Agle TRT

    Check for the diagram to get more info about the program
*/

#include <string.h>

enum STATE {CHECK=0, READY=1, CHARGE=2, C_DONE=3, ERROR=-1, UNSAFE=-2, EXIT=-3}; //Status codes
enum E_COD {BATTERY_TEMP, OVERCHARGE, CURRENT_DRAWN}; //Error codes

int doCheck(){
    //Checks whether the pig/fans/brusa are attached to the handcart
    //returns READY state in case of the presence of all of them
    //returns CHECK state in case of the miss of one of them
}

int doReady(){
    //Pig/fans/brusa are attached and ready to charge
    //waits for user input to start charging
}

int doCharge(){
    //pig is charging, fans are blowing
    //Periodically checks battery status, returns ERROR state in case of failure
    //Returns C_DONE in case of a well done charge
}

int doError(){
    //something gone wrong, check last_err variable
    //if there is some dangerous situation, return UNSAFE state
    //if there are no dangerous situation, stop the program or continue (?)
}

int doUnsafe(){
    //based on the type of problem, discharge or cool down the pig
    //in example, on BATTERY_TEMP error, 100% fan
    //to decide what to do on end of unsafe
}

int doState(int state){
    switch(state){
        case CHECK:
            return doCheck();
        break;
        case READY:
            return doReady();
        break;
        case CHARGE:
            return doCharge();
        break;
        case C_DONE:
            return doC_done();
        break;
        case ERROR:
            return doError();
        break;
        case UNSAFE:
            return doUnsafe();
        break;
        case EXIT:
            return EXIT;
        break;
    }
}

int act_stat = CHECK;
int last_err = -1;

int main(int argc, int* argv){
    while (1){
        int next_stat = doState(act_stat);
        if (next_stat == EXIT){
            return 0;
        }
        act_stat = next_stat;
    }
}   